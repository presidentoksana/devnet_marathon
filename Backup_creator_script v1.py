#!/usr/bin/env python
# """Module docstring."""

# Imports python
from netmiko import ConnectHandler
import csv
import logging
import datetime
import multiprocessing as mp
import difflib
import filecmp
import sys
import os

# Module 'Global' variables
DEVICE_FILE_PATH = 'inventory.csv' # file should contain a list of devices in format: ip,hostname,username,password,device_type
CHANGELOG_FILE_NAME = 'changelog.txt' # file will be created to log changes
BACKUPLOG_FILE_NAME = 'backup_log.txt' # file contains a list of backups

def enable_logging():
    # This function enables netmiko logging for reference
    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    logger = logging.getLogger("netmiko")

def get_devices_from_file(device_file):
    # This function takes a CSV file with inventory and creates a python list of dictionaries out of it.
    # Each dictionary contains information about a single device.

    # creating empty structures
    device_list = list()
    device = dict()

    # reading a CSV file with ',' as a delimeter
    with open(device_file, 'r') as f:
        reader = csv.reader(f, delimiter=',')
        # knowing that the first row is a header, skipping it
        next(reader, None)
        # for the following rows unparsing data to the dictionary
        for row in reader:
            print('Iventory file contains the following device: '+str(row))
            print('-*-' * 10)
            device['ip'] = row[0]
            device['username'] = row[1]
            device['password'] = row[2]
            device['device_type'] = row[3]
            device['secret'] = row[4]
            device['hostname'] = row[5]
            device_list.append(device)

    # returning a list of dictionaries
    return device_list

def get_current_date_and_time():
    # This function returns the current date and time
    # Format: yyyy_mm_dd-hh_mm

    now = datetime.datetime.now()

    #creating a formatted string
    timestamp = str(now.year) + '_' + str(now.month) + '_' + str(now.day) + '-' + str(now.hour) + '_' + str(now.minute)

    # returns a string
    return timestamp

def connect_to_device(device_to_connect):
    # This function opens a connection to the device using Netmiko
    # Requires a device dictionary as an input
    # The second possible implementation could look like:
    # connection = Netmiko(host = device['ip'], username = device['username'], password=device['password'],device_type=device['device_type'])

    # connecting
    connection = ConnectHandler (
        host = device_to_connect['ip'],
        username = device_to_connect['username'],
        password=device_to_connect['password'],
        device_type=device_to_connect['device_type'],
        secret=device_to_connect['secret']
    )

    print ('Opened connection to '+device_to_connect['ip'])
    print('-*-' * 10)

    # returns a "connection" object
    return connection

def disconnect_from_device(connection):
    #This function terminates the connection to the device

    connection.disconnect()
    print ('Connection terminated')
    print('-*-' * 10)

def create_backup_directory(hostname):
    # This function creates a folder for each device if this folder doesn't exist
    # Folder name equals device hostname
    # Requires hostname as an input

    # getting a path to the current working directory
    path = os.getcwd()
    # creating a path to the new directory
    path = path+"/"+hostname

    # if this directory doesn't exist, it gets created
    # ignored otherwise
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        print("Creation of the directory %s failed" % path)
        print('-*-' * 10)
    else:
        print("Successfully created the directory %s" % path)
        print('-*-' * 10)

    # returns a path to the new directory
    return path

def create_backup_file_name(hostname, today):
    # This function creates a backup file name (a string)
    # Requires hostname and timestamp strings as an input

    # backup file name structure is hostname-yyyy_mm_dd-hh_mm
    backup_file_name = hostname + '-' + today + '.txt'
    print('Backup file name will be '+backup_file_name)
    print('-*-' * 10)

    # returns a string
    return backup_file_name

def log_backups (last_backup, logfile_name):
    # This function creates a file (if not present) and writes every new backup file name to the end of this file
    # As a result there is a file with contents of the directory
    # Requires the name of the last backup file and the name of a log file

    with open(logfile_name, 'a+') as file:
        file.write(last_backup+'\n')
    print(last_backup + ' is added to the log file')
    print('-*-'*10)

def create_backup(connection, backup_file_name, log_file_name, hostname):
    # This function pulls running configuration from a device and writes it to the backup file
    # Requires as an input:
    # - connection object,
    # - backup file path
    # - log file path (the file with a list of backup files)
    # - device hostname

    # sending a CLI command using Netmiko and printing an output
    # should enter enable mode first
    connection.enable()
    output = connection.send_command('sh run')
    print('\n')
    print('Running configuration is... \n' + output)
    print('#' * 30 + '\n'*3)
    print('-*-' * 10)

    #creating a backup file and writing command output to it
    with open(backup_file_name, 'w') as file:
        file.write(output)
    print("Backup of " + hostname + " is complete!")
    print('-*-' * 10)

    # call a function to add this new backup file to a log-list
    log_backups(backup_file_name, log_file_name)

def get_previous_backup_file(logfile_name):
    # This function returns the name of a previous backup file if it exists in the directory
    # Requires the path to the log file (a file with the list of all backups) as an input

    # reading from the log file to the list
    with open (logfile_name,'r') as f1:
        backup_list = f1.read().splitlines()

        # if there is more than 1 backup, take the second latest
        if len(backup_list)>1:
            previous_backup = backup_list[-2]

        # if there is just a single backup, inform the user
        else:
            previous_backup = 'nothing to compare to'

    # returns the path to the precious backup or 'nothing to compare to'
    return previous_backup

def compare_backup_with_the_previous(backup_file, changelog_file, log_file):
    # This function compares created backup with the previous one and writes delta to the changelog file
    # Requires as an input:
    # - a path to the backup file,
    # - a path to changelog file
    # - a path to a backup log file (with a list of backups)

    # call a function to get the previous backup file name from a backup log file
    # if there are no backups in a directory, it returns 'nothing to compare to'
    previous_backup_file = get_previous_backup_file(log_file)

    # if there was an earlier backup, comparing the new one to it
    if previous_backup_file != 'nothing to compare to':

        # checking if files differ from each other
        if not filecmp.cmp(previous_backup_file, backup_file):

            # if they do differ, open backup files in read mode and open/create changelog file for appending
            with open(previous_backup_file,'r') as f1, open(backup_file,'r') as f2, open(changelog_file,'a+') as f3:

                # looking for delta
                delta = difflib.unified_diff(f1.read().splitlines(),f2.read().splitlines())

                # writing discovered delta to the changelog file
                f3.write(backup_file + ' contains the following changes comparing to '+ previous_backup_file + ':\n')
                f3.write('\n'.join(delta))
                f3.write('\n'+'*'*20 + '\n'*5)
            print ('Logged changes to ' + changelog_file)
            print('-*-' * 10)


        else:
            # if there is no difference, leave a comment to the changelog file
            with open(changelog_file,'a+') as f3:
                print(backup_file,' contains 0 changes comparing to ',previous_backup_file,':\n')
                f3.write(backup_file + ' contains 0 changes comparing to '+ previous_backup_file + ':\n')
                f3.write('\n'+'*' * 20 + '\n'*5)
            print ('There are no changes to log this time')
            print('-*-' * 10)

    else:
        print ('There is nothing to compare the following backup to this time: ',backup_file)
        print('-*-' * 10)

def process_target(device,timestamp):
    # This function will be run by each of the processes in parallel
    # This function implements a logic for a single device using other functions defined above:
    #  - creates a directory for backups if it doesn't exist,
    #  - creates full path to backup related files,
    #  - connects to the device,
    #  - creates a backup for this device,
    #  - terminates connection,
    #  - compares a backup to the previous one and logs the delta
    # Requires connection object and a timestamp string as an input

    path = create_backup_directory(device['hostname'])

    # creating a path to all files to be created
    backup_file_path = path+'/'+create_backup_file_name(device['hostname'], timestamp)
    backuplog_file_path = path +'/'+ BACKUPLOG_FILE_NAME
    changelog_file_path = path +'/'+ CHANGELOG_FILE_NAME

    # connecting to a device
    connection = connect_to_device(device)

    # creating a backup file and terminating connection
    create_backup(connection, backup_file_path, backuplog_file_path, device['hostname'])
    disconnect_from_device(connection)

    # comparing to the previous backup
    compare_backup_with_the_previous(backup_file_path, changelog_file_path, backuplog_file_path)

def main(*args):
    # This is a main function

    # getting the timestamp string
    timestamp = get_current_date_and_time()

    # getting a device list from the file in a python format
    device_list = get_devices_from_file(DEVICE_FILE_PATH)

    # creating a blanc list
    processes=list()

    # creating a dedicated process for each device and adding to the list
    for device in device_list:
        processes.append(mp.Process(target=process_target,args=(device,timestamp)))

    print ('Starting several processes...')
    # starting processes
    for process in processes:
        process.start()

    print('Merging several processes...')
    # waiting for processes to finish before executing the rest of the script
    for process in processes:
        process.join()

if __name__ == '__main__':
    # checking if we run independently
    _, *script_args = sys.argv

    # the execution starts here
    main(*script_args)







