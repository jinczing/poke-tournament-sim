import json
import os
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import random
from timeit import default_timer as timer
from tqdm import tqdm, trange

# ANSI color codes for styling
COLORS = {
    "blue": "\033[94m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "white": "\033[97m",
    "reset": "\033[0m"
}

def load_builds(file_path):
    builds = {}
    current_key = None
    current_lines = []
    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f.readlines():
            if raw_line.startswith("|"):
                if current_key is not None:
                    if current_key in builds:
                        raise ValueError(f"Duplicate build key: {current_key}")
                    builds[current_key] = current_lines
                key_line = raw_line[1:].strip()
                if "#" not in key_line:
                    raise ValueError(f"Missing build id in line: {raw_line.strip()}")
                pokemon, local_id = key_line.rsplit("#", 1)
                current_key = (pokemon.strip(), int(local_id))
                current_lines = []
            else:
                if current_key is None:
                    if raw_line.strip() == "":
                        continue
                    raise ValueError("Build data found before any build header.")
                current_lines.append(raw_line)
    if current_key is not None:
        if current_key in builds:
            raise ValueError(f"Duplicate build key: {current_key}")
        builds[current_key] = current_lines
    return builds

def write_builds_to_file(builds_by_key, build_refs, file_path, setLevel):
    with open(file_path, "w") as f:
        f.truncate(0)  # Clear the file
        for pokemon, local_id in build_refs:
            build_key = (pokemon, int(local_id))
            build_lines = builds_by_key.get(build_key)
            if build_lines is None:
                raise KeyError(f"Build not found: {build_key}")
            for line in build_lines:
                if setLevel is not None and line.startswith("Level: "):
                    f.write(f"Level: {setLevel}\n")
                else:
                    f.write(line)
            f.write("\n")  # Add a newline to separate builds

# =============================================================================
# Runs a single simulation for some matchup passed in
# =============================================================================
def runSimulation(matchup, threadNo, builds_by_key, teams_by_leader, setLevel):
    leader_1, leader_2 = matchup
    team1 = teams_by_leader[leader_1]
    team2 = teams_by_leader[leader_2]
    team1No = leader_1
    team2No = leader_2

    game = str(len(team1)) + "v" + str(len(team2))

    # Process the first group of builds
    write_builds_to_file(builds_by_key, team1, f"./WorkerFiles/{threadNo}1.txt", setLevel)
    # Process the second group of builds
    write_builds_to_file(builds_by_key, team2, f"./WorkerFiles/{threadNo}2.txt", setLevel)
    RetryCount = 0
    while True:
        #mycommand = "cd ../pokemon-showdown && node build && node ./dist/sim/examples/battle-stream-example"
        mycommand = "cd ../pokemon-showdown && node ./dist/sim/examples/Simulation-test-1 " + threadNo + " " + str(team1No) + " " + str(team2No)
        result = subprocess.getoutput(mycommand)
        # if the battle fails we retry, sometimes showdown fails for some unexpected reason
        if not (result.startswith("node:internal") or result.startswith("TypeError") or result.startswith("runtime") or re.search(r'Node\.js\s+v\d+\.\d+\.\d+$', result[-30:])):
            try:
                if not (result[:40].split("\n")[2].startswith("TypeError")):
                    break
                else:
                    if RetryCount > 9:
                        print("Error occurred with battle 10 times, skipping " + game)
                        RetryCount = 0
                        with open ("./ErrorOutputs.txt", "a") as o: 
                            o.write(result + "\n]]]]]\n")
                        break
                    RetryCount += 1
            except:
                print("Unexpected error occurred with battle, skipping " + game)
                RetryCount = 0
                with open ("./ErrorOutputs.txt", "a") as o: 
                    o.write(result + "\n]]]]]\n")
                break
        else:
            if RetryCount > 9:
                print("node:internal error, TypeError or runtime error occurred with battle, skipping " + game)
                RetryCount = 0
                with open ("./ErrorOutputs.txt", "a") as o: 
                    o.write(result + "\n]]]]]\n")
                break
            RetryCount += 1
    with open ("./WorkerOutputs/" + threadNo + ".txt", "a") as o: 
        o.write(result + "\n]]]]]\n")

    try:
        # Extract the "vs" line
        vs_line = next((line for line in result.splitlines() if " vs " in line), "Unknown vs Match")
        trainer_1, trainer_2 = vs_line.split(" vs ")
        vs_line_colored = (
            f"{COLORS['red']}{trainer_1}{COLORS['reset']} "
            f"{COLORS['white']}vs{COLORS['reset']} "
            f"{COLORS['blue']}{trainer_2}{COLORS['reset']}"
        )
        
        # Extract the names of the trainers from the "vs" line
        trainer_1, trainer_2 = vs_line.split(" vs ")
        
        # Determine the victor from the result
        win_line = next((line for line in result.splitlines() if "|win|" in line), "")
        if "|win|Bot 1" in win_line:
            victor = trainer_1
        elif "|win|Bot 2" in win_line:
            victor = trainer_2
        else:
            victor = "Unknown"

        # Uncomment if you want to display each individual fight result as it runs
            # Note: may slow down total time to run sims
        # tqdm.write(
        #     f"{COLORS['yellow']}Finished Running Simulation{COLORS['reset']} "
        #     f"{vs_line_colored} | "
        #     f"Victor: "
        #     f"{COLORS['green']}{victor}{COLORS['reset']}"
        # )
    
    except Exception as e:
        pass
    return(result)
    
builds_filename = "Inputs/" + "GymLeaderPokemon_v2.txt"
noOfThreads = 10 # change this to fit your CPU
RandomiseTeams = False # randomise order of simulations

#read in teams
with open('Inputs/tournament_battles_v2.json', 'r', encoding='utf-8') as infile:
    teams = json.load(infile)
if RandomiseTeams:
    random.shuffle(teams)

with open('Inputs/GymLeaderTeams_v2.json', 'r', encoding='utf-8') as infile:
    teams_by_leader = json.load(infile)

print(len(teams))
setLevel = 50 # If not None, all pokemon will be set to this level
n = 10 # number of battles to stop running after
teams = teams[:n] # comment this out to simulate all battles

n = len(teams)
noOfTeams = len(teams_by_leader)

with open ("./output.txt", "a") as o: 
    o.truncate(0)
with open ("./ErrorOutputs.txt", "a") as o: 
    o.truncate(0)

# combine the individual worker outputs into one
infiles = [str(i+1) for i in range(noOfThreads)]
infiles.append("0")
# clear worker outputs
for i in infiles:
    with open("./WorkerOutputs/" + i + ".txt", "w") as output:
        output.truncate(0)

subprocess.getoutput("cd ../pokemon-showdown && node build")
threads = []
start = time.time()

lock = threading.Lock()
lock2 = threading.Lock()
condition = threading.Condition(lock)

thread_names = [str(i+1) for i in range(noOfThreads)]

simulation_counter = 0
simulations_since_last_update = 0

builds_by_key = load_builds(builds_filename)

# Function to submit simulations and manage thread names
def submit_simulation(executor, team):
    global simulation_counter
    global simulations_since_last_update
    with condition:  # Use condition variable to wait for an available thread name
        while not thread_names:
            condition.wait()  # Wait for a thread name to become available
        thread_name = thread_names.pop(0)  # Allocate a thread name
    
    # Define a callback function to release the thread name back to the pool and notify waiting threads
    def release_thread_name(future):
        global simulation_counter
        global simulations_since_last_update
        with condition:
            # print("releasing thread", thread_name)
            thread_names.append(thread_name)
            condition.notify()  # Notify one waiting thread that a thread name has become available
            simulation_counter += 1
            simulations_since_last_update += 1
            if simulations_since_last_update >= 50 and len(teams) != 0 and simulation_counter > 0:
                simulations_since_last_update = 0
                current_runtime = time.time() - start
                average_time_per_simulation = current_runtime / simulation_counter if simulation_counter else float('inf')
                estimated_remaining_time = average_time_per_simulation * len(teams)

                seconds = round(estimated_remaining_time)
                minutes, seconds = divmod(seconds, 60)
                hours, minutes = divmod(minutes, 60)

                # Format the remaining time based on its length
                if hours > 0:
                    formatted_time = f"{hours} hour(s), {minutes} minute(s)"
                elif minutes > 0:
                    formatted_time = f"{minutes} minute(s), {seconds} second(s)"
                else:
                    formatted_time = f"{seconds} second(s)"

    # Submit the task
    future = executor.submit(runSimulation, team, thread_name, builds_by_key, teams_by_leader, setLevel)
    # Attach the callback to the future
    future.add_done_callback(release_thread_name)

# Initialize progress bar
total_teams = len(teams)
desc = f"{COLORS['yellow']}Processing Teams{COLORS['reset']}"
bar_format = (
    "{desc}: "  # Description with color
    f"{COLORS['green']}{{n_fmt}}/{COLORS['blue']}{{total_fmt}}{COLORS['reset']} "  # Current iteration and total in color
    "{percentage:3.0f}%|{bar}| "  # Percentage and bar
    f"{COLORS['green']}Elapsed: {{elapsed}}{COLORS['reset']} "  # Elapsed time in color
    f"{COLORS['blue']}Remaining: {{remaining}}{COLORS['reset']}"  # Remaining time in color
)
progress_bar = trange(total_teams, desc=desc, dynamic_ncols=True, leave=True, mininterval=0.5, bar_format=bar_format, position=2)

with ThreadPoolExecutor(max_workers=noOfThreads) as executor:
    while teams:
        with lock2:
            if teams:
                team = teams.pop(0)
                submit_simulation(executor, team)
                progress_bar.update(1)  # Update progress bar each time a team is processed

progress_bar.close()  # Close progress bar when done
print(len(teams))  # Keeping track of remaining teams
end = time.time()

with open("output.txt", "a") as outfile:
    for i in infiles:
        with open("./WorkerOutputs/" + i + ".txt", "r") as output:
            for i in output.readlines():
                outfile.write(i)

# clear worker outputs
for i in infiles:
    with open("./WorkerOutputs/" + i + ".txt", "w") as output:
        output.truncate(0)
            
print("ran in " + str(end-start) + " Seconds Overall")
print(str((end - start)/n) + " Seconds Per Sim On Average")
