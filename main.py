from functools import partial
import curses
import os
import json
import subprocess
import datetime
import calendar
import sys
import time
import multiprocessing

def render_table(app_data, stdscr):

    row_line = app_data["row_line"]
    menu_topology = app_data["menu_topology"]

    stdscr.clear()

    for i, key in enumerate(menu_topology):
        if row_line == i:
            stdscr.addstr(i, 0, '--> ' + key + ' <--', curses.A_STANDOUT)
        else:
            stdscr.addstr(i, 0, key)

    app_data["row_count"] = len(menu_topology)


def redraw_line(app_data, stdscr):
    row_line = app_data["row_line"]
    row_count = app_data["row_count"]
    if row_line != 0:
        stdscr.move(row_line - 1, 0)
        stdscr.clrtoeol()
        top_line = list(app_data["menu_topology"].keys())[row_line - 1]
        stdscr.addstr(row_line - 1, 0, top_line)

    selected_line = list(app_data["menu_topology"].keys())[row_line]
    stdscr.addstr(row_line, 0, '--> ' + selected_line + ' <--', curses.A_STANDOUT)

    if row_line != row_count - 1:
        stdscr.move(row_line + 1, 0)
        stdscr.clrtoeol()
        bottom_line = list(app_data["menu_topology"].keys())[row_line + 1]
        stdscr.addstr(row_line + 1, 0, bottom_line)


def main(app_data, stdscr):

    row_line = app_data["row_line"]
    row_count = app_data["row_count"]

    render_table(app_data, stdscr)

    while True:
        row_count = app_data["row_count"]

        curses.curs_set(0)

        redraw_line(app_data, stdscr)

        user_input = stdscr.get_wch()

        if user_input == curses.KEY_DOWN:
            row_line += 1
            if row_line >= row_count:
                row_line = row_count - 1
        elif user_input == curses.KEY_UP:
            row_line -= 1
            if row_line < 0:
                row_line = 0
        # This is the escape key
        elif user_input == "\x1b":
            app_data["menu_topology"] = app_data["prior_menu_topology"]
            render_table(app_data, stdscr)
        elif user_input == "q":
            app_data["should_exit"] = True
        # 10 is enter if not a number pad
        elif user_input == "\n":
            app_data["menu_topology"] = list(app_data["menu_topology"].values())[row_line]
            app_data["row_line"] = 0
            row_line = 0
            if "script" in app_data["menu_topology"] :
                break
            else:
                render_table(app_data, stdscr)

        app_data["row_line"] = row_line

        if app_data["should_exit"]:
            break


config_file_handler = open('time_config.json')
time_configuration = json.load(config_file_handler)
config_file_handler.close()

time_log_handler = open('time.json')
time_ledger = json.load(time_log_handler)
time_log_handler.close()

def validate_whitelisted_days():
    no_time_to_play = time_configuration["no_time_to_play"]
    today = datetime.datetime.today()
    day_of_week = today.weekday()
    time_saver_trigger = time_configuration["time_saver_trigger"]
    if os.path.exists(time_saver_trigger):
        whitelisted_days = time_configuration["whitelisted_days"]
        day_is_not_allowed = True
        for day in whitelisted_days:
            if calendar.day_name[day_of_week] == day:
                day_is_not_allowed = False

        if day_is_not_allowed:
            print(no_time_to_play)
            sys.exit(42)

def time_counter_loop(args):
    current_time = args
    first_warning = False
    final_warning = False
    while True:
        current_time += 1
        time.sleep(1)
        if current_time > time_configuration["first_warning_time"] and first_warning == False:
            first_warning_hook = time_configuration["first_warning_hook"]
            first_warning = True
            subprocess.call(first_warning_hook, shell=True)
        if current_time > time_configuration["final_warning_time"] and final_warning == False:
            final_warning_hook = time_configuration["final_warning_hook"]
            final_warning = True
            subprocess.call(final_warning_hook, shell=True)


def execute_program_with_time_logging(script_path):

    time_saver_trigger = time_configuration["time_saver_trigger"]

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

        print(current_time_total)

        if current_time_total >= time_configuration["first_warning_time"]:
            print(time_configuration["time_limit_reached"])
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


with open('config.json', 'r') as file:
    menu_topology = json.load(file)

app_data = {
    "row_line": 0,
    "should_exit": False,
    "row_count": len(menu_topology),
    "menu_topology": menu_topology,
    "prior_menu_topology": menu_topology
}

# Some terminals set a very high delay for escape, overwrite this
os.environ.setdefault('ESCDELAY', str(5))
# Open the ncurses interface and selection
# appdata menu_topology key will mutate for a command to run
curses.wrapper(partial(main, app_data))
# If we should not launching a program with a time restriction exit the program
is_logging_time = False
if "time_limit" in app_data["menu_topology"]:
    if app_data["menu_topology"]["time_limit"] == True:
        # We assume the time_config.json file is present if you are doing time options
        # Seeing as otherwise it will crash\not do anything
        validate_whitelisted_days()
        is_logging_time = True
# Execute the selected program; people may leave empty strings while testing
# So just ignore this input
if app_data["menu_topology"]["script"] != "":
    if is_logging_time:
        execute_program_with_time_logging(app_data["menu_topology"]["script"])
    else:
        subprocess.run([app_data["menu_topology"]["script"]]) 
