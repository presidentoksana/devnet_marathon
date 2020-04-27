#!/usr/bin/env python
# """Module docstring."""

#Imports
from netmiko import ConnectHandler
import csv
import logging
import datetime
import multiprocessing as mp
import difflib
import filecmp
import sys
import os

#Module 'Global' variables
DEVICE_FILE_PATH = 'devices.csv' # file should contain a list of devices in format: ip,username,password,device_type
BACKUP_DIR_PATH = '/Users/otselova/PycharmProjects/backup_creator_v2/backups' # complete path to backup directory

def enable_logging():
    # This function enables netmiko logging for reference

    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    logger = logging.getLogger("netmiko")

def get_devices_from_file(device_file):
    # This function takes a CSV file with inventory and creates a python list of dictionaries out of it
    # Each disctionary contains information about a single device

    # creating empty structures
    device_list = list()
    device = dict()

    # reading a CSV file with ',' as a delimeter
    with open(device_file, 'r') as f:
        reader = csv.DictReader(f, delimiter=',')

        # every device represented by single row which is a dictionary object with keys equal to column names.
        for row in reader:
            device_list.append(row)

    print ("Got the device list from inventory")
    print('-*-' * 10)
    print ()

    # returning a list of dictionaries
    return device_list

def get_current_date_and_time():
    # This function returns the current date and time
    now = datetime.datetime.now()

    print("Got a timestamp")
    print('-*-' * 10)
    print()

    # Returning a formatted date string
    # Format: yyyy_mm_dd-hh_mm_ss
    return now.strftime("%Y_%m_%d-%H_%M_%S")

def connect_to_device(device):
    # This function opens a connection to the device using Netmiko
    # Requires a device dictionary as an input

    # Since there is a 'hostname' key, this dictionary can't be used as is
    connection = ConnectHandler(
        host = device['ip'],
        username = device['username'],
        password=device['password'],
        device_type=device['device_type'],
        secret=device['secret']
    )

    print ('Opened connection to '+device['ip'])
    print('-*-' * 10)
    print()

    # returns a "connection" object
    return connection

def disconnect_from_device(connection, hostname):
    #This function terminates the connection to the device

    connection.disconnect()
    print ('Connection to device {} terminated'.format(hostname))

def get_backup_file_path(hostname,timestamp):
    # This function creates a backup file name (a string)
    # backup file path structure is hostname/hostname-yyyy_mm_dd-hh_mm

    # checking if backup directory exists for the device, creating it if not present
    if not os.path.exists(os.path.join(BACKUP_DIR_PATH, hostname)):
        os.mkdir(os.path.join(BACKUP_DIR_PATH, hostname))

    # Merging a string to form a full backup file name
    backup_file_path = os.path.join(BACKUP_DIR_PATH, hostname, '{}-{}.txt'.format(hostname, timestamp))
    print('Backup file path will be '+backup_file_path)
    print('-*-' * 10)
    print()

    # returning backup file path
    return backup_file_path

def create_backup(connection, backup_file_path, hostname):
    # This function pulls running configuration from a device and writes it to the backup file
    # Requires connection object, backup file path and a device hostname as an input

    try:
        # sending a CLI command using Netmiko and printing an output
        connection.enable()
        output = connection.send_command('sh run')

        # creating a backup file and writing command output to it
        with open(backup_file_path, 'w') as file:
            file.write(output)
        print("Backup of " + hostname + " is complete!")
        print('-*-' * 10)
        print()

        # if successfully done
        return True

    except Error:
        # if there was an error
        print('Error! Unable to backup device ' + hostname)
        return False


def get_previous_backup_file_path(hostname, curent_backup_file_path):
    # This function looks for the previous backup file in a directory
    # Requires a hostname and the latest backup file name as an input

    # removing the full path
    current_backup_filename = curent_backup_file_path.split('/')[-1]

    # creatting an empty dictionary to keep backup file names
    backup_files = {}

    # looking for previous backup files
    for file_name in os.listdir(os.path.join(BACKUP_DIR_PATH, hostname)):

        # select files with correct extension and names
        if file_name.endswith('.txt') and file_name != current_backup_filename:

            # getting backup date and time from filename
            filename_datetime = datetime.datetime.strptime(file_name.strip('.txt')[len(hostname)+1:],'%Y_%m_%d-%H_%M_%S')

            # adding backup files to dict with key equal to datetime in unix format
            backup_files[filename_datetime.strftime('%s')] = file_name

    if len(backup_files) > 0:

        # getting the previous backup filename
        previous_backup_key = sorted(backup_files.keys(), reverse=True)[0]
        previous_backup_file_path = os.path.join(BACKUP_DIR_PATH, hostname, backup_files[previous_backup_key])

        print("Found a previous backup ", previous_backup_file_path)
        print('-*-' * 10)
        print()

        # returning the previous backup file
        return previous_backup_file_path
    else:
        return False


def compare_backup_with_previous_config(previous_backup_file_path, backup_file_path):
    # This function compares created backup with the previous one and writes delta to the changelog file
    # Requires a path to last backup file and a path to the previous backup file as an input

    # creating a name for changelog file
    changes_file_path = backup_file_path.strip('.txt') + '.changes'

    # checking if files differ from each other
    if not filecmp.cmp(previous_backup_file_path, backup_file_path):
        print('Comparing configs:')
        print('\tCurrent backup: {}'.format(backup_file_path))
        print('\tPrevious backup: {}'.format(previous_backup_file_path))
        print('\tChanges: {}'.format(changes_file_path))
        print('-*-' * 10)
        print()

        # if they do differ, open files in read mode and open changelog in write mode
        with open(previous_backup_file_path,'r') as f1, open(backup_file_path,'r') as f2, open(changes_file_path,'w') as f3:
            # looking for delta
            delta = difflib.unified_diff(f1.read().splitlines(),f2.read().splitlines())
            # writing discovered delta to the changelog file
            f3.write('\n'.join(delta))
        print ('\tConfig state: changed')
        print('-*-' * 10)
        print()

    else:
        print('Config was not changed since the latest version.')
        print('-*-' * 10)
        print()

def process_target(device,timestamp):
    # This function will be run by each of the processes in parallel
    # This function implements a logic for a single device using other functions defined above:
    #  - connects to the device,
    #  - gets a backup file name and a hostname for this device,
    #  - creates a backup for this device
    #  - terminates connection
    #  - compares a backup to the golden configuration and logs the delta
    # Requires connection object and a timestamp string as an input

    connection = connect_to_device(device)
    
    backup_file_path = get_backup_file_path(device['hostname'], timestamp)
    backup_result = create_backup(connection, backup_file_path, device['hostname'])
    
    disconnect_from_device(connection, device['hostname'])

    # if the script managed to create a backup, then look for a previous one
    if backup_result:
        previous_backup_file_path = get_previous_backup_file_path(device['hostname'], backup_file_path)

        # if the previous one exists, compare
        if previous_backup_file_path:
            compare_backup_with_previous_config(previous_backup_file_path, backup_file_path)
        else:
            print('Unable to find previos backup file to find changes.')
            print('-*-' * 10)
            print()

def main(*args):
    # This is a main function

    # Enable logs
    enable_logging()

    # getting the timestamp string
    timestamp = get_current_date_and_time()

    # getting a device list from the file in a python format
    device_list = get_devices_from_file(DEVICE_FILE_PATH)

    # creating a empty list
    processes=list()

    # Running workers to manage connections
    with mp.Pool(4) as pool:
        # Starting several processes...
        for device in device_list:
            processes.append(pool.apply_async(process_target, args=(device,timestamp)))
        # Waiting for results...
        for process in processes:
            process.get()


if __name__ == '__main__':
    # checking if we run independently
    _, *script_args = sys.argv
    
    # the execution starts here
    main(*script_args)







