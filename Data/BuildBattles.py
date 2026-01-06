import json
from itertools import combinations

def generate_tournament_matchups(input_file, output_file):
    # How many times to run each battle
    RUN_N_TIMES = 100

    # Read the JSON data from the input file
    with open(input_file, 'r', encoding='utf-8') as file:
        gym_leaders_data = json.load(file)

    # Use leader names so matchups don't duplicate full team data
    leaders = list(gym_leaders_data.keys())

    # Generate all possible pairs of teams for the tournament
    # Each matchup is repeated 100 times
    matchups = [[leader1, leader2] for leader1, leader2 in combinations(leaders, 2) for _ in range(RUN_N_TIMES)]

    print(len(matchups))

    # Write the matchups to the output JSON file
    with open(output_file, 'w') as file:
        json.dump(matchups, file, indent=2)

# Example usage:
# generate_tournament_matchups('Inputs/tournament_battles/Badge7Battles.json', 'Inputs/tournament_battles.json')
generate_tournament_matchups('Inputs/GymLeaderTeams.json', 'Inputs/tournament_battles.json')
