import datetime
import calendar
import json
import sys
import os
import subprocess
import time
import multiprocessing

config_file_handler = open('ci_launcher.json')
configuration = json.load(config_file_handler)
config_file_handler.close()

time_log_handler = open('time.json')
time_ledger = json.load(time_log_handler)
time_log_handler.close()

script_dir_base = ""
if "script_dir_base" in configuration:
    script_dir_base = configuration["script_dir_base"] + "/"


def validate_whitelisted_days():
    no_time_to_play = configuration["no_time_to_play"]
    today = datetime.datetime.today()
    day_of_week = today.weekday()
    time_saver_trigger = configuration["time_saver_trigger"]
    if os.path.exists(time_saver_trigger):
        whitelisted_days = configuration["whitelisted_days"]
        day_is_not_allowed = True
        for day in whitelisted_days:
            if calendar.day_name[day_of_week] == day:
                day_is_not_allowed = False

        if day_is_not_allowed:
            print(no_time_to_play)
            sys.exit(42)


def load_dir_data():
    dirs_configuration = configuration["dir_map_configuration_location"]
    dirs_configuration_handler = open(dirs_configuration, "r")
    dir_data = {}
    for line in dirs_configuration_handler.readlines():
        line_parts = line.strip().split("=")
        dir_data[line_parts[0]] = {
            "desc": line_parts[1],
            "scripts": os.listdir(script_dir_base + line_parts[0])
        }
    return dir_data


def list_programs(dir_data):
    if not configuration["hide_dir_desc"]:
        for dir in dir_data:
            desc = dir_data[dir]["desc"]
            print("\033[94m\033[1m" + desc + "\033[0m")
            scripts = sorted(dir_data[dir]["scripts"])
            for script in scripts:
                print("\033[92m" + script + "\033[0m")
    else:
        scripts = []
        for dir in dir_data:
            scripts_dir = dir_data[dir]["scripts"]
            scripts += scripts_dir
        scripts = sorted(scripts)
        alternative_desc = configuration["alternative_desc"]
        print("\033[94m\033[1m" + alternative_desc + "\033[0m")
        for script in scripts:
            print("\033[92m" + script + "\033[0m")


def find_script_path(dir_data):
    script_name = sys.argv[1]
    script_path = ""
    for dir in dir_data:
        script_path = script_dir_base + dir + "/" + script_name
        if os.path.exists(script_path):
            break
    return script_path


def time_counter_loop(args):
    current_time = args
    first_warning = False
    final_warning = False
    while True:
        current_time += 1
        time.sleep(1)
        if current_time > configuration["first_warning_time"] and first_warning == False:
            first_warning_hook = configuration["first_warning_hook"]
            first_warning = True
            subprocess.call(first_warning_hook, shell=True)
        if current_time > configuration["final_warning_time"] and final_warning == False:
            final_warning_hook = configuration["final_warning_hook"]
            final_warning = True
            subprocess.call(final_warning_hook, shell=True)


def execute_program(script_path):

    time_saver_trigger = configuration["time_saver_trigger"]

    if os.path.exists(time_saver_trigger):
        week_number = int(datetime.datetime.today().strftime("%V"))
        if time_ledger["week_number"] != week_number:
            time_ledger["week_number"] = week_number
            time_ledger["ledger"] = {}
        today = datetime.datetime.today()
        day_of_week = str(today.weekday())
        if day_of_week not in time_ledger["ledger"]:
            time_ledger["ledger"][day_of_week] = {}

        start_time = int(time.time())

        current_time_total = 0
        for time_record in time_ledger["ledger"][day_of_week]:
            current_time_total += (time_ledger["ledger"][day_of_week][time_record] - int(time_record))

        if current_time_total >= configuration["first_warning_time"]:
            print(configuration["time_limit_reached"])
            return

        time_ledger["ledger"][day_of_week][start_time] = None

        thread = multiprocessing.Process(target = time_counter_loop, args = (current_time_total, ))
        thread.start()

    subprocess.call(script_path, shell=True)

    if os.path.exists(time_saver_trigger):
        end_time = int(time.time())
        time_ledger["ledger"][day_of_week][start_time] = end_time

        thread.terminate()

        with open('time.json', "w") as file_handler:
            json.dump(time_ledger, file_handler, indent=4)
        file_handler.close()


def execute_or_list_programs(dir_data):
    if len(sys.argv) == 1:
        list_programs(dir_data)
    else:
        script_path = find_script_path(dir_data)
        execute_program(script_path)


validate_whitelisted_days()
dir_data = load_dir_data()
execute_or_list_programs(dir_data)
