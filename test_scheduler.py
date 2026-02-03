#!/usr/bin/env python3
"""
CPU Scheduler Testing Framework
===============================

This module provides a comprehensive test harness for validating CPU scheduler 
implementations. It:

1. Generates test process files with various scheduling scenarios
2. Runs the scheduler executable with different algorithms and parameters
3. Parses the CSV output from the scheduler
4. Compares results against expected outcomes
5. Reports detailed test results with clear pass/fail indications

The framework tests multiple scheduling algorithms:
- First-Come, First-Served (FCFS)
- Shortest Job First (SJF)
- Shortest Remaining Time First (SRTF)
- Round-Robin (RR) with configurable quantum

It also tests various edge cases:
- Priority inversion scenarios
- Many short jobs (starvation potential)
- Multiple CPUs
- Simultaneous job arrivals
- Tie-breaking rules

Usage:
    python test_scheduler.py [options]

Options:
    --executable PATH    Path to the scheduler executable
    --algorithm ALGO     Run only tests for specified algorithm
    --test NAME          Run only the specified test
    --verbose            Show detailed scheduler output
    --no-cleanup         Keep generated test files

Example:
    # Compile your scheduler
    gcc scheduler.c -o scheduler -lm
    
    # Run the tests
    python test_scheduler.py --verbose
"""

import subprocess
import csv
import io
import os
import math
import argparse
import sys
from typing import Dict, List, Tuple, Optional, Any, Union

# --- Configuration ---
SCHEDULER_EXECUTABLE = './scheduler'  # Default path to scheduler executable
FLOAT_TOLERANCE = 0.01  # Tolerance for floating-point comparisons
DEFAULT_TIMEOUT = 10    # Default timeout in seconds

# --- ANSI Color Codes ---
_supports_color = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and sys.platform != 'win32'

COLOR_GREEN = "\033[92m" if _supports_color else ""
COLOR_RED = "\033[91m" if _supports_color else ""
COLOR_YELLOW = "\033[93m" if _supports_color else ""
COLOR_CYAN = "\033[96m" if _supports_color else ""
COLOR_BOLD = "\033[1m" if _supports_color else ""
COLOR_RESET = "\033[0m" if _supports_color else ""

# --- Types ---
TestCase = Tuple[str, str, int, int, str, Dict[str, List[Dict[str, str]]]]
ResultsDict = Dict[str, List[Dict[str, str]]]


# --- Helper Functions ---
def run_scheduler(executable: str, algorithm: str, cpus: int, quantum: int, 
                  input_file: str, verbose: bool = False) -> Optional[str]:
    """
    Run the CPU scheduler executable with the specified parameters.
    
    Args:
        executable: Path to the scheduler executable
        algorithm: Scheduling algorithm (FCFS, SJF, SRTF, RR)
        cpus: Number of CPUs
        quantum: Time quantum for Round Robin (ignored for other algorithms)
        input_file: Path to the process input file
        verbose: Whether to print the scheduler's output
        
    Returns:
        The stdout output from the scheduler, or None if execution failed
    """
    cmd = [
        executable,
        '-f', input_file,
        '-a', algorithm,
        '-c', str(cpus)
    ]
    if algorithm == 'RR':
        cmd.extend(['-q', str(quantum)])

    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=DEFAULT_TIMEOUT)
        print("Scheduler execution successful.")
        
        if verbose:
            print("\nScheduler Output:")
            print("-" * 40)
            print(result.stdout)
            print("-" * 40)
            
        return result.stdout
    except FileNotFoundError:
        print(f"{COLOR_RED}Error: Scheduler executable not found at '{executable}'{COLOR_RESET}")
        return None
    except subprocess.CalledProcessError as e:
        print(f"{COLOR_RED}Error running scheduler: {e}{COLOR_RESET}")
        print(f"Stderr:\n{e.stderr}")
        return None
    except subprocess.TimeoutExpired:
        print(f"{COLOR_RED}Error: Scheduler process timed out after {DEFAULT_TIMEOUT}s.{COLOR_RESET}")
        return None


def parse_csv_section(output_lines: List[str], section_header: str) -> Optional[List[Dict[str, str]]]:
    """
    Parse a specific CSV section from the scheduler's output.
    
    This function extracts and parses a CSV section with the given header from 
    the scheduler's output lines, handling the format where CSV data is preceded 
    by section headers and may include blank lines.
    
    Args:
        output_lines: List of text output lines from the scheduler
        section_header: Text header identifying the section to parse
        
    Returns:
        List of dictionaries, each representing a row of CSV data with column names 
        as keys, or None if parsing fails
    """
    data = []
    in_section = False
    header_found = False
    csv_content = io.StringIO()

    for line in output_lines:
        stripped_line = line.strip()
        if section_header in stripped_line:
            in_section = True
            header_found = False  # Reset header flag when section starts
            csv_content = io.StringIO()  # Reset content for new section
            continue

        if in_section:
            # Stop if we hit the end marker or another section header
            if "--- End CSV Output ---" in stripped_line or \
               ("--- CSV Output ---" in stripped_line and section_header not in stripped_line) or \
               ("Stats (CSV):" in stripped_line and section_header not in stripped_line):
                break
                
            # Skip blank lines within the section before the header
            if not stripped_line and not header_found:
                continue
                
            # The first non-blank line after the header is the CSV header
            if not header_found and stripped_line:
                # Check if it looks like a CSV header (contains commas)
                if ',' in stripped_line:
                    header_found = True
                    csv_content.write(stripped_line + '\n')
                # else: skip potential non-header lines like section titles
            elif header_found and stripped_line:
                csv_content.write(stripped_line + '\n')

    csv_content.seek(0)  # Rewind the string buffer
    if header_found:
        try:
            # Use DictReader for easier access by column name
            reader = csv.DictReader(csv_content)
            data = [row for row in reader]
        except Exception as e:
            print(f"{COLOR_RED}Error parsing CSV for section '{section_header}': {e}{COLOR_RESET}")
            print(f"Content attempted to parse:\n{csv_content.getvalue()}")
            return None  # Indicate parsing failure

    return data


def parse_all_csv(output: str) -> Optional[ResultsDict]:
    """
    Parse all CSV sections from the scheduler's output.
    
    Extracts the three main CSV sections: process stats, CPU stats, and average stats.
    
    Args:
        output: The complete stdout text from the scheduler
        
    Returns:
        Dictionary containing the parsed data for each section, or None if parsing failed
    """
    if output is None:
        return None

    lines = output.splitlines()
    results = {}

    results['process'] = parse_csv_section(lines, 'Process Stats (CSV):')
    results['cpu'] = parse_csv_section(lines, 'CPU Stats (CSV):')
    results['average'] = parse_csv_section(lines, 'Average Stats (CSV):')

    # Check if parsing failed for any section
    if results['process'] is None or results['cpu'] is None or results['average'] is None:
        print(f"{COLOR_RED}CSV Parsing failed for one or more sections.{COLOR_RESET}")
        return None
    if not results['process'] or not results['cpu'] or not results['average']:
        print(f"{COLOR_YELLOW}Warning: One or more CSV sections were empty.{COLOR_RESET}")

    return results


def compare_floats(val1_str: str, val2_str: str, tolerance: float) -> bool:
    """
    Compare two floating-point values with tolerance.
    
    Args:
        val1_str: First value as string
        val2_str: Second value as string
        tolerance: Acceptable difference between values
        
    Returns:
        True if the values are equal within tolerance, False otherwise
    """
    if val1_str == 'N/A' and val2_str == 'N/A':
        return True
    if val1_str == 'N/A' or val2_str == 'N/A':
        return False
    try:
        return math.isclose(float(val1_str), float(val2_str), abs_tol=tolerance)
    except ValueError:
        return False  # Cannot convert to float


def compare_ints(val1_str: str, val2_str: str) -> bool:
    """
    Compare two integer values.
    
    Args:
        val1_str: First value as string
        val2_str: Second value as string
        
    Returns:
        True if the values are equal, False otherwise
    """
    if val1_str == 'N/A' and val2_str == 'N/A':
        return True
    if val1_str == 'N/A' or val2_str == 'N/A':
        return False
    try:
        return int(val1_str) == int(val2_str)
    except ValueError:
        return False  # Cannot convert to int


def compare_results(actual: ResultsDict, expected: ResultsDict) -> List[str]:
    """
    Compare actual scheduler results against expected results.
    
    Performs detailed comparison of process stats, CPU stats, and averages,
    generating informative mismatch messages.
    
    Args:
        actual: Dictionary of actual results from the scheduler
        expected: Dictionary of expected results
        
    Returns:
        List of mismatch messages, empty if all results match expectations
    """
    mismatches = []

    # Compare Process Stats
    if len(actual.get('process', [])) != len(expected.get('process', [])):
        mismatches.append(f"Process count mismatch: Expected {len(expected.get('process', []))}, "
                          f"Got {len(actual.get('process', []))}")
    else:
        # Ensure expected columns exist before trying to access them
        expected_process_cols = expected.get('process', [{}])[0].keys() if expected.get('process') else []
        for i, (act_row, exp_row) in enumerate(zip(actual.get('process', []), expected.get('process', []))):
            for col in expected_process_cols:  # Iterate over expected columns
                if col not in act_row:
                    mismatches.append(f"Process row {i+1}: Missing column '{col}' in actual output")
                    continue
                    
                # Determine comparison type based on column name
                if col in ["PID", "Arrival", "Burst", "Priority", "Start", "Finish", "Turnaround", "Waiting", "Response"]:
                    if not compare_ints(act_row[col], exp_row[col]):
                        mismatches.append(f"Process row {i+1}, Col '{col}': "
                                          f"Expected '{exp_row[col]}', Got '{act_row[col]}'")

    # Compare CPU Stats
    if len(actual.get('cpu', [])) != len(expected.get('cpu', [])):
        mismatches.append(f"CPU count mismatch: Expected {len(expected.get('cpu', []))}, "
                          f"Got {len(actual.get('cpu', []))}")
    else:
        expected_cpu_cols = expected.get('cpu', [{}])[0].keys() if expected.get('cpu') else []
        for i, (act_row, exp_row) in enumerate(zip(actual.get('cpu', []), expected.get('cpu', []))):
            for col in expected_cpu_cols:
                if col not in act_row:
                    mismatches.append(f"CPU row {i+1}: Missing column '{col}' in actual output")
                    continue
                    
                if col in ["CPU_ID", "BusyTime", "IdleTime"]:
                    if not compare_ints(act_row[col], exp_row[col]):
                        mismatches.append(f"CPU row {i+1}, Col '{col}': "
                                          f"Expected '{exp_row[col]}', Got '{act_row[col]}'")
                elif col in ["Utilization%"]:
                    if not compare_floats(act_row[col], exp_row[col], FLOAT_TOLERANCE):
                        mismatches.append(f"CPU row {i+1}, Col '{col}': "
                                          f"Expected '{exp_row[col]}', Got '{act_row[col]}'")

    # Compare Average Stats
    if len(actual.get('average', [])) != 1 or len(expected.get('average', [])) != 1:
        mismatches.append(f"Average stats row count mismatch: "
                          f"Expected 1, Got {len(actual.get('average', []))}")
    elif actual.get('average') and expected.get('average'):  # Check if lists are not empty
        expected_avg_cols = expected['average'][0].keys()
        act_avg = actual['average'][0]
        exp_avg = expected['average'][0]
        
        for col in expected_avg_cols:
            if col not in act_avg:
                mismatches.append(f"Average stats: Missing column '{col}' in actual output")
                continue
                
            if col in ["AvgTurnaround", "AvgWaiting", "AvgResponse"]:
                if not compare_floats(act_avg[col], exp_avg[col], FLOAT_TOLERANCE):
                    mismatches.append(f"Average stats, Col '{col}': "
                                      f"Expected '{exp_avg[col]}', Got '{act_avg[col]}'")

    return mismatches


# --- Test File Generation Functions ---

def create_test_files() -> Dict[str, str]:
    """
    Create all test input files needed for the test cases.
    
    Returns:
        Dictionary mapping test file identifiers to their file paths
    """
    test_files = {}
    
    # Basic test file
    test_files['basic'] = 'test_processes_basic.txt'
    with open(test_files['basic'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 5 1\n")
        f.write("2 2 3 2\n")
        f.write("3 4 2 1\n")

    # Priority test file
    test_files['priority'] = 'test_processes_priority.txt'
    with open(test_files['priority'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 5 2\n")  # P1: Higher priority than P2
        f.write("2 2 3 1\n")  # P2: Lower priority
        f.write("3 2 4 3\n")  # P3: Highest priority, arrives same time as P2
        f.write("4 5 2 2\n")  # P4: Arrives later

    # Burst time ties
    test_files['ties'] = 'test_processes_ties.txt'
    with open(test_files['ties'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 3 1\n")    # Arrives at 0, burst=3, lowest priority
        f.write("2 0 3 2\n")    # Arrives at 0, burst=3, medium priority
        f.write("3 0 3 3\n")    # Arrives at 0, burst=3, highest priority

    # Simultaneous arrivals
    test_files['simultaneous'] = 'test_processes_simultaneous.txt'
    with open(test_files['simultaneous'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 4 2\n")
        f.write("2 0 3 1\n")
        f.write("3 0 2 3\n")

    # Scenario two (longer test case)
    test_files['scenario_two'] = 'test_processes_scenario_two.txt'
    with open(test_files['scenario_two'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 8 2\n")
        f.write("2 1 2 3\n")
        f.write("3 2 4 1\n")
        f.write("4 3 6 2\n")
        f.write("5 4 7 3\n")
        f.write("6 5 5 1\n")

    # Many short jobs test
    test_files['short_jobs'] = 'test_processes_short_jobs.txt'
    with open(test_files['short_jobs'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 10 2\n")     # Long job, medium priority
        f.write("2 1 12 1\n")     # Long job, low priority
        f.write("3 2 1 3\n")      # Short job, high priority
        f.write("4 3 2 2\n")      # Short job, medium priority
        f.write("5 4 1 3\n")      # Short job, high priority
        f.write("6 5 1 1\n")      # Short job, low priority
        f.write("7 6 2 2\n")      # Short job, medium priority
        f.write("8 7 1 3\n")      # Short job, high priority
        f.write("9 8 2 1\n")      # Short job, low priority
        f.write("10 9 1 2\n")     # Short job, medium priority

    # Priority inversion scenario
    test_files['priority_inversion'] = 'test_processes_priority_inversion.txt'
    with open(test_files['priority_inversion'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 6 1\n")      # Low priority, arrives first
        f.write("2 1 2 5\n")      # Highest priority, arrives second
        f.write("3 2 3 4\n")      # High priority, arrives third
        f.write("4 3 1 3\n")      # Medium priority
        f.write("5 4 2 2\n")      # Low-medium priority
    
        # --- NEW EDGE-CASE TEST FILES ---

    # Idle gap before first arrival (CPU should be idle initially)
    test_files['idle_gap'] = 'test_processes_idle_gap.txt'
    with open(test_files['idle_gap'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 3 2 1\n")
        f.write("2 5 1 1\n")

    # More CPUs than processes + simultaneous arrivals (tests dispatch + idle CPUs)
    test_files['few_procs_many_cpus'] = 'test_processes_few_procs_many_cpus.txt'
    with open(test_files['few_procs_many_cpus'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 4 1\n")
        f.write("2 0 2 2\n")
        f.write("3 0 1 3\n")

    # FCFS input file intentionally unsorted by arrival (scheduler must not trust file order)
    test_files['unsorted_arrivals'] = 'test_processes_unsorted_arrivals.txt'
    with open(test_files['unsorted_arrivals'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("2 5 1 1\n")
        f.write("1 0 3 1\n")
        f.write("3 2 2 1\n")

    # SJF tie on burst: choose higher priority, then lower PID
    test_files['sjf_tie_priority'] = 'test_processes_sjf_tie_priority.txt'
    with open(test_files['sjf_tie_priority'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 3 1\n")
        f.write("2 0 3 5\n")
        f.write("3 0 1 2\n")

    # SRTF multiple preemption chain
    test_files['srtf_preempt_chain'] = 'test_processes_srtf_preempt_chain.txt'
    with open(test_files['srtf_preempt_chain'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 8 1\n")
        f.write("2 1 4 1\n")
        f.write("3 2 2 1\n")

    # SRTF tie on remaining time: break tie via priority, then PID
    test_files['srtf_equal_remaining'] = 'test_processes_srtf_equal_remaining.txt'
    with open(test_files['srtf_equal_remaining'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 4 1\n")
        f.write("2 1 3 5\n")

    # Single process that arrives late (tests idle and correctness of stats)
    test_files['single_late'] = 'test_processes_single_late.txt'
    with open(test_files['single_late'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 5 3 1\n")

    # RR quantum=1 with simultaneous arrivals (tests extreme switching + tie-breaking)
    test_files['rr_q1_simul'] = 'test_processes_rr_q1_simul.txt'
    with open(test_files['rr_q1_simul'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 0 2 1\n")
        f.write("2 0 2 2\n")

    # RR with idle gap then multi-quantum completion
    test_files['rr_idle_single'] = 'test_processes_rr_idle_single.txt'
    with open(test_files['rr_idle_single'], 'w') as f:
        f.write("# PID Arrival Burst Priority\n")
        f.write("1 3 3 1\n")


    return test_files


def cleanup_test_files(test_files: Dict[str, str], keep_files: bool = False) -> None:
    """
    Clean up generated test files.
    
    Args:
        test_files: Dictionary of test file paths to remove
        keep_files: If True, files will not be removed
    """
    if keep_files:
        print(f"{COLOR_YELLOW}Keeping generated test files as requested{COLOR_RESET}")
        return
        
    print("Cleaning up generated test files...")
    for filepath in test_files.values():
        try:
            os.remove(filepath)
            print(f"  Removed {filepath}")
        except OSError:
            pass  # Ignore if file doesn't exist


# --- Test Case Definitions ---

def define_test_cases(test_files: Dict[str, str]) -> List[TestCase]:
    """
    Define all test cases with their expected results.
    
    Args:
        test_files: Dictionary mapping test file identifiers to their file paths
        
    Returns:
        List of test case tuples
    """
    # Organize test cases by algorithm for better readability
    fcfs_tests = [
        # FCFS with 1 CPU
        (
            "FCFS_1CPU", "FCFS", 1, 0, test_files['basic'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '1', 'Start': '0', 'Finish': '5', 'Turnaround': '5', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '2', 'Start': '5', 'Finish': '8', 'Turnaround': '6', 'Waiting': '3', 'Response': '3'},
                    {'PID': '3', 'Arrival': '4', 'Burst': '2', 'Priority': '1', 'Start': '8', 'Finish': '10', 'Turnaround': '6', 'Waiting': '4', 'Response': '4'}
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '10', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '5.67', 'AvgWaiting': '2.33', 'AvgResponse': '2.33'}
                ]
            }
        ),
        # FCFS with 2 CPUs
        (
            "FCFS_2CPU", "FCFS", 2, 0, test_files['basic'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '1', 'Start': '0', 'Finish': '5', 'Turnaround': '5', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '2', 'Start': '2', 'Finish': '5', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                    {'PID': '3', 'Arrival': '4', 'Burst': '2', 'Priority': '1', 'Start': '5', 'Finish': '7', 'Turnaround': '3', 'Waiting': '1', 'Response': '1'}
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '7', 'IdleTime': '0', 'Utilization%': '100.00'},
                    {'CPU_ID': '1', 'BusyTime': '3', 'IdleTime': '4', 'Utilization%': '42.86'}
                ],
                'average': [
                    {'AvgTurnaround': '3.67', 'AvgWaiting': '0.33', 'AvgResponse': '0.33'}
                ]
            }
        ),
        # FCFS with simultaneous arrivals
        (
            "FCFS_SIMULTANEOUS", "FCFS", 1, 0, test_files['simultaneous'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '4', 'Priority': '2', 'Start': '2', 'Finish': '6', 'Turnaround': '6', 'Waiting': '2', 'Response': '2'},
                    {'PID': '2', 'Arrival': '0', 'Burst': '3', 'Priority': '1', 'Start': '6', 'Finish': '9', 'Turnaround': '9', 'Waiting': '6', 'Response': '6'},
                    {'PID': '3', 'Arrival': '0', 'Burst': '2', 'Priority': '3', 'Start': '0', 'Finish': '2', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [{'CPU_ID': '0', 'BusyTime': '9', 'IdleTime': '0', 'Utilization%': '100.00'}],
                'average': [{'AvgTurnaround': '5.67', 'AvgWaiting': '2.67', 'AvgResponse': '2.67'}]
            }
        ),
        # FCFS longer scenario
        (
            "FCFS_Scenario2", "FCFS", 1, 0, test_files['scenario_two'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '8', 'Priority': '2', 'Start': '0', 'Finish': '8', 'Turnaround': '8', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '1', 'Burst': '2', 'Priority': '3', 'Start': '8', 'Finish': '10', 'Turnaround': '9', 'Waiting': '7', 'Response': '7'},
                    {'PID': '3', 'Arrival': '2', 'Burst': '4', 'Priority': '1', 'Start': '10', 'Finish': '14', 'Turnaround': '12', 'Waiting': '8', 'Response': '8'},
                    {'PID': '4', 'Arrival': '3', 'Burst': '6', 'Priority': '2', 'Start': '14', 'Finish': '20', 'Turnaround': '17', 'Waiting': '11', 'Response': '11'},
                    {'PID': '5', 'Arrival': '4', 'Burst': '7', 'Priority': '3', 'Start': '20', 'Finish': '27', 'Turnaround': '23', 'Waiting': '16', 'Response': '16'},
                    {'PID': '6', 'Arrival': '5', 'Burst': '5', 'Priority': '1', 'Start': '27', 'Finish': '32', 'Turnaround': '27', 'Waiting': '22', 'Response': '22'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '32', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '16.00', 'AvgWaiting': '10.67', 'AvgResponse': '10.67'}
                ]
            }
        ),
        # FCFS priority inversion test
        (
            "FCFS_PRIORITY_INVERSION", "FCFS", 1, 0, test_files['priority_inversion'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '6', 'Priority': '1', 'Start': '0', 'Finish': '6', 'Turnaround': '6', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '1', 'Burst': '2', 'Priority': '5', 'Start': '6', 'Finish': '8', 'Turnaround': '7', 'Waiting': '5', 'Response': '5'},
                    {'PID': '3', 'Arrival': '2', 'Burst': '3', 'Priority': '4', 'Start': '8', 'Finish': '11', 'Turnaround': '9', 'Waiting': '6', 'Response': '6'},
                    {'PID': '4', 'Arrival': '3', 'Burst': '1', 'Priority': '3', 'Start': '11', 'Finish': '12', 'Turnaround': '9', 'Waiting': '8', 'Response': '8'},
                    {'PID': '5', 'Arrival': '4', 'Burst': '2', 'Priority': '2', 'Start': '12', 'Finish': '14', 'Turnaround': '10', 'Waiting': '8', 'Response': '8'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '14', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '8.20', 'AvgWaiting': '5.40', 'AvgResponse': '5.40'}
                ]
            }
        ),
                # FCFS with initial idle gap
        (
            "FCFS_IDLE_GAP_1CPU", "FCFS", 1, 0, test_files['idle_gap'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '3', 'Burst': '2', 'Priority': '1', 'Start': '3', 'Finish': '5', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '5', 'Burst': '1', 'Priority': '1', 'Start': '5', 'Finish': '6', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '3', 'IdleTime': '3', 'Utilization%': '50.00'}
                ],
                'average': [
                    {'AvgTurnaround': '1.50', 'AvgWaiting': '0.00', 'AvgResponse': '0.00'}
                ]
            }
        ),

        # FCFS with more CPUs than processes (simultaneous arrivals)
        (
            "FCFS_4CPU_FEW_PROCS", "FCFS", 4, 0, test_files['few_procs_many_cpus'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '4', 'Priority': '1', 'Start': '0', 'Finish': '4', 'Turnaround': '4', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '0', 'Burst': '2', 'Priority': '2', 'Start': '0', 'Finish': '2', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'},
                    {'PID': '3', 'Arrival': '0', 'Burst': '1', 'Priority': '3', 'Start': '0', 'Finish': '1', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '1', 'IdleTime': '3', 'Utilization%': '25.00'},
                    {'CPU_ID': '1', 'BusyTime': '2', 'IdleTime': '2', 'Utilization%': '50.00'},
                    {'CPU_ID': '2', 'BusyTime': '4', 'IdleTime': '0', 'Utilization%': '100.00'},
                    {'CPU_ID': '3', 'BusyTime': '0', 'IdleTime': '4', 'Utilization%': '0.00'},
                ],
                'average': [
                    {'AvgTurnaround': '2.33', 'AvgWaiting': '0.00', 'AvgResponse': '0.00'}
                ]
            }
        ),

        # FCFS with unsorted input file (must schedule by arrival, not file order)
        (
            "FCFS_UNSORTED_INPUT", "FCFS", 1, 0, test_files['unsorted_arrivals'],
            {
               'process': [
                    {'PID': '2', 'Arrival': '5', 'Burst': '1', 'Priority': '1', 'Start': '5', 'Finish': '6', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                    {'PID': '1', 'Arrival': '0', 'Burst': '3', 'Priority': '1', 'Start': '0', 'Finish': '3', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                    {'PID': '3', 'Arrival': '2', 'Burst': '2', 'Priority': '1', 'Start': '3', 'Finish': '5', 'Turnaround': '3', 'Waiting': '1', 'Response': '1'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '6', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '2.33', 'AvgWaiting': '0.33', 'AvgResponse': '0.33'}
                ]
            }
        ),

    ]

    sjf_tests = [
        # SJF with 1 CPU
        (
            "SJF_1CPU", "SJF", 1, 0, test_files['basic'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '1', 'Start': '0', 'Finish': '5', 'Turnaround': '5', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '2', 'Start': '7', 'Finish': '10', 'Turnaround': '8', 'Waiting': '5', 'Response': '5'},
                    {'PID': '3', 'Arrival': '4', 'Burst': '2', 'Priority': '1', 'Start': '5', 'Finish': '7', 'Turnaround': '3', 'Waiting': '1', 'Response': '1'}
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '10', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '5.33', 'AvgWaiting': '2.00', 'AvgResponse': '2.00'}
                ]
            }
        ),
        # SJF with ties
        (
            "SJF_TIES", "SJF", 1, 0, test_files['ties'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '3', 'Priority': '1', 'Start': '6', 'Finish': '9', 'Turnaround': '9', 'Waiting': '6', 'Response': '6'},
                    {'PID': '2', 'Arrival': '0', 'Burst': '3', 'Priority': '2', 'Start': '3', 'Finish': '6', 'Turnaround': '6', 'Waiting': '3', 'Response': '3'},
                    {'PID': '3', 'Arrival': '0', 'Burst': '3', 'Priority': '3', 'Start': '0', 'Finish': '3', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [{'CPU_ID': '0', 'BusyTime': '9', 'IdleTime': '0', 'Utilization%': '100.00'}],
                'average': [{'AvgTurnaround': '6.00', 'AvgWaiting': '3.00', 'AvgResponse': '3.00'}]
            }
        ),
                # SJF with initial idle gap
        (
            "SJF_IDLE_GAP_1CPU", "SJF", 1, 0, test_files['idle_gap'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '3', 'Burst': '2', 'Priority': '1', 'Start': '3', 'Finish': '5', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '5', 'Burst': '1', 'Priority': '1', 'Start': '5', 'Finish': '6', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '3', 'IdleTime': '3', 'Utilization%': '50.00'}
                ],
                'average': [
                    {'AvgTurnaround': '1.50', 'AvgWaiting': '0.00', 'AvgResponse': '0.00'}
                ]
            }
        ),

        # SJF tie on burst length: break tie by priority, then PID
        (
            "SJF_TIE_PRIORITY_PID", "SJF", 1, 0, test_files['sjf_tie_priority'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '3', 'Priority': '1', 'Start': '4', 'Finish': '7', 'Turnaround': '7', 'Waiting': '4', 'Response': '4'},
                    {'PID': '2', 'Arrival': '0', 'Burst': '3', 'Priority': '5', 'Start': '1', 'Finish': '4', 'Turnaround': '4', 'Waiting': '1', 'Response': '1'},
                    {'PID': '3', 'Arrival': '0', 'Burst': '1', 'Priority': '2', 'Start': '0', 'Finish': '1', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '7', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '4.00', 'AvgWaiting': '1.67', 'AvgResponse': '1.67'}
                ]
            }
        ),

    ]

    srtf_tests = [
        # SRTF with 1 CPU
        (
            "SRTF_1CPU", "SRTF", 1, 0, test_files['basic'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '1', 'Start': '0', 'Finish': '10', 'Turnaround': '10', 'Waiting': '5', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '2', 'Start': '2', 'Finish': '5', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                    {'PID': '3', 'Arrival': '4', 'Burst': '2', 'Priority': '1', 'Start': '5', 'Finish': '7', 'Turnaround': '3', 'Waiting': '1', 'Response': '1'}
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '10', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '5.33', 'AvgWaiting': '2.00', 'AvgResponse': '0.33'}
                ]
            }
        ),
        # SRTF with 2 CPUs
        (
            "SRTF_2CPU", "SRTF", 2, 0, test_files['basic'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '1', 'Start': '0', 'Finish': '5', 'Turnaround': '5', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '2', 'Start': '2', 'Finish': '5', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                    {'PID': '3', 'Arrival': '4', 'Burst': '2', 'Priority': '1', 'Start': '5', 'Finish': '7', 'Turnaround': '3', 'Waiting': '1', 'Response': '1'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '7', 'IdleTime': '0', 'Utilization%': '100.00'},
                    {'CPU_ID': '1', 'BusyTime': '3', 'IdleTime': '4', 'Utilization%': '42.86'}
                ],
                'average': [
                    {'AvgTurnaround': '3.67', 'AvgWaiting': '0.33', 'AvgResponse': '0.33'}
                ]
            }
        ),
        # SRTF with priority
        (
            "SRTF_1CPU_Priority", "SRTF", 1, 0, test_files['priority'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '2', 'Start': '0', 'Finish': '5', 'Turnaround': '5', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '1', 'Start': '7', 'Finish': '10', 'Turnaround': '8', 'Waiting': '5', 'Response': '5'},
                    {'PID': '3', 'Arrival': '2', 'Burst': '4', 'Priority': '3', 'Start': '10', 'Finish': '14', 'Turnaround': '12', 'Waiting': '8', 'Response': '8'},
                    {'PID': '4', 'Arrival': '5', 'Burst': '2', 'Priority': '2', 'Start': '5', 'Finish': '7', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'}
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '14', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '6.75', 'AvgWaiting': '3.25', 'AvgResponse': '3.25'}
                ]
            }
        ),
        # SRTF with many short jobs (starvation test)
        (
            "SRTF_SHORT_JOBS", "SRTF", 1, 0, test_files['short_jobs'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '10', 'Priority': '2', 'Start': '0', 'Finish': '21', 'Turnaround': '21', 'Waiting': '11', 'Response': '0'},
                    {'PID': '2', 'Arrival': '1', 'Burst': '12', 'Priority': '1', 'Start': '21', 'Finish': '33', 'Turnaround': '32', 'Waiting': '20', 'Response': '20'},
                    {'PID': '3', 'Arrival': '2', 'Burst': '1', 'Priority': '3', 'Start': '2', 'Finish': '3', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                    {'PID': '4', 'Arrival': '3', 'Burst': '2', 'Priority': '2', 'Start': '3', 'Finish': '6', 'Turnaround': '3', 'Waiting': '1', 'Response': '0'},
                    {'PID': '5', 'Arrival': '4', 'Burst': '1', 'Priority': '3', 'Start': '4', 'Finish': '5', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                    {'PID': '6', 'Arrival': '5', 'Burst': '1', 'Priority': '1', 'Start': '6', 'Finish': '7', 'Turnaround': '2', 'Waiting': '1', 'Response': '1'},
                    {'PID': '7', 'Arrival': '6', 'Burst': '2', 'Priority': '2', 'Start': '8', 'Finish': '10', 'Turnaround': '4', 'Waiting': '2', 'Response': '2'},
                    {'PID': '8', 'Arrival': '7', 'Burst': '1', 'Priority': '3', 'Start': '7', 'Finish': '8', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                    {'PID': '9', 'Arrival': '8', 'Burst': '2', 'Priority': '1', 'Start': '11', 'Finish': '13', 'Turnaround': '5', 'Waiting': '3', 'Response': '3'},
                    {'PID': '10', 'Arrival': '9', 'Burst': '1', 'Priority': '2', 'Start': '10', 'Finish': '11', 'Turnaround': '2', 'Waiting': '1', 'Response': '1'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '33', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '7.20', 'AvgWaiting': '3.90', 'AvgResponse': '2.70'}
                ]
            }
        ),
        # SRTF priority inversion test
        (
            "SRTF_PRIORITY_INVERSION", "SRTF", 1, 0, test_files['priority_inversion'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '6', 'Priority': '1', 'Start': '0', 'Finish': '14', 'Turnaround': '14', 'Waiting': '8', 'Response': '0'},
                    {'PID': '2', 'Arrival': '1', 'Burst': '2', 'Priority': '5', 'Start': '1', 'Finish': '3', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'},
                    {'PID': '3', 'Arrival': '2', 'Burst': '3', 'Priority': '4', 'Start': '6', 'Finish': '9', 'Turnaround': '7', 'Waiting': '4', 'Response': '4'},
                    {'PID': '4', 'Arrival': '3', 'Burst': '1', 'Priority': '3', 'Start': '3', 'Finish': '4', 'Turnaround': '1', 'Waiting': '0', 'Response': '0'},
                    {'PID': '5', 'Arrival': '4', 'Burst': '2', 'Priority': '2', 'Start': '4', 'Finish': '6', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '14', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '5.20', 'AvgWaiting': '2.40', 'AvgResponse': '0.80'}
                ]
            }
        ),
                # SRTF preemption chain (multiple preempts)
        (
            "SRTF_PREEMPT_CHAIN", "SRTF", 1, 0, test_files['srtf_preempt_chain'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '8', 'Priority': '1', 'Start': '0', 'Finish': '14', 'Turnaround': '14', 'Waiting': '6', 'Response': '0'},
                    {'PID': '2', 'Arrival': '1', 'Burst': '4', 'Priority': '1', 'Start': '1', 'Finish': '7', 'Turnaround': '6', 'Waiting': '2', 'Response': '0'},
                    {'PID': '3', 'Arrival': '2', 'Burst': '2', 'Priority': '1', 'Start': '2', 'Finish': '4', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '14', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '7.33', 'AvgWaiting': '2.67', 'AvgResponse': '0.00'}
                ]
            }
        ),

        # SRTF tie on remaining time: priority breaks tie, then PID
        (
            "SRTF_TIE_REMAIN_PRIORITY", "SRTF", 1, 0, test_files['srtf_equal_remaining'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '4', 'Priority': '1', 'Start': '0', 'Finish': '7', 'Turnaround': '7', 'Waiting': '3', 'Response': '0'},
                    {'PID': '2', 'Arrival': '1', 'Burst': '3', 'Priority': '5', 'Start': '1', 'Finish': '4', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '7', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '5.00', 'AvgWaiting': '1.50', 'AvgResponse': '0.00'}
                ]
            }
        ),

        # SRTF single process arrives late (idle time + start/finish correctness)
        (
            "SRTF_SINGLE_LATE", "SRTF", 1, 0, test_files['single_late'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '5', 'Burst': '3', 'Priority': '1', 'Start': '5', 'Finish': '8', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '3', 'IdleTime': '5', 'Utilization%': '37.50'}
                ],
                'average': [
                    {'AvgTurnaround': '3.00', 'AvgWaiting': '0.00', 'AvgResponse': '0.00'}
                ]
            }
        ),

    ]

    rr_tests = [
        # RR with quantum 2
        (
            "RR_1CPU_Q2", "RR", 1, 2, test_files['basic'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '1', 'Start': '0', 'Finish': '10', 'Turnaround': '10', 'Waiting': '5', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '2', 'Start': '2', 'Finish': '9', 'Turnaround': '7', 'Waiting': '4', 'Response': '0'},
                    {'PID': '3', 'Arrival': '4', 'Burst': '2', 'Priority': '1', 'Start': '6', 'Finish': '8', 'Turnaround': '4', 'Waiting': '2', 'Response': '2'}
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '10', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '7.00', 'AvgWaiting': '3.67', 'AvgResponse': '0.67'}
                ]
            }
        ),
        # RR with large quantum (should behave like FCFS)
        (
            "RR_1CPU_Q10", "RR", 1, 10, test_files['basic'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '1', 'Start': '0', 'Finish': '5', 'Turnaround': '5', 'Waiting': '0', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '2', 'Start': '5', 'Finish': '8', 'Turnaround': '6', 'Waiting': '3', 'Response': '3'},
                    {'PID': '3', 'Arrival': '4', 'Burst': '2', 'Priority': '1', 'Start': '8', 'Finish': '10', 'Turnaround': '6', 'Waiting': '4', 'Response': '4'}
                ],
                'cpu': [{'CPU_ID': '0', 'BusyTime': '10', 'IdleTime': '0', 'Utilization%': '100.00'}],
                'average': [{'AvgTurnaround': '5.67', 'AvgWaiting': '2.33', 'AvgResponse': '2.33'}]
            }
        ),
        # RR with 2 CPUs
        (
            "RR_2CPU_Q2", "RR", 2, 2, test_files['basic'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '5', 'Priority': '1', 'Start': '0', 'Finish': '6', 'Turnaround': '6', 'Waiting': '1', 'Response': '0'},
                    {'PID': '2', 'Arrival': '2', 'Burst': '3', 'Priority': '2', 'Start': '2', 'Finish': '5', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                    {'PID': '3', 'Arrival': '4', 'Burst': '2', 'Priority': '1', 'Start': '4', 'Finish': '6', 'Turnaround': '2', 'Waiting': '0', 'Response': '0'}
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '6', 'IdleTime': '0', 'Utilization%': '100.00'},
                    {'CPU_ID': '1', 'BusyTime': '4', 'IdleTime': '2', 'Utilization%': '66.67'}
                ],
                'average': [
                    {'AvgTurnaround': '3.67', 'AvgWaiting': '0.33', 'AvgResponse': '0.00'}
                ]
            }
        ),
                # RR quantum=1 with simultaneous arrivals (stress switching + tie-breaking)
        (
            "RR_1CPU_Q1_SIMUL", "RR", 1, 1, test_files['rr_q1_simul'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '0', 'Burst': '2', 'Priority': '1', 'Start': '1', 'Finish': '4', 'Turnaround': '4', 'Waiting': '2', 'Response': '1'},
                    {'PID': '2', 'Arrival': '0', 'Burst': '2', 'Priority': '2', 'Start': '0', 'Finish': '3', 'Turnaround': '3', 'Waiting': '1', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '4', 'IdleTime': '0', 'Utilization%': '100.00'}
                ],
                'average': [
                    {'AvgTurnaround': '3.50', 'AvgWaiting': '1.50', 'AvgResponse': '0.50'}
                ]
            }
        ),

        # RR with idle gap then multi-quantum completion
        (
            "RR_1CPU_IDLE_GAP_Q2", "RR", 1, 2, test_files['rr_idle_single'],
            {
                'process': [
                    {'PID': '1', 'Arrival': '3', 'Burst': '3', 'Priority': '1', 'Start': '3', 'Finish': '6', 'Turnaround': '3', 'Waiting': '0', 'Response': '0'},
                ],
                'cpu': [
                    {'CPU_ID': '0', 'BusyTime': '3', 'IdleTime': '3', 'Utilization%': '50.00'}
                ],
                'average': [
                    {'AvgTurnaround': '3.00', 'AvgWaiting': '0.00', 'AvgResponse': '0.00'}
                ]
            }
        ),

    ]

    # Combine all tests
    return fcfs_tests + sjf_tests + srtf_tests + rr_tests


def run_tests(executable_path: str, tests: List[TestCase], verbose: bool = False) -> Tuple[int, int]:
    """
    Run multiple scheduler tests and report results.
    
    Args:
        executable_path: Path to the scheduler executable
        tests: List of test case tuples to run
        verbose: Whether to show detailed scheduler output
        
    Returns:
        Tuple containing (passed_count, total_count)
    """
    total_tests = len(tests)
    passed_tests = 0

    print(f"{COLOR_CYAN}--- Running {total_tests} Test Cases ---{COLOR_RESET}")

    for name, algo, cpus, quantum, infile, expected in tests:
        print(f"\n{COLOR_YELLOW}--- Test: {name} ({algo}, {cpus} CPU(s), "
              f"Q={quantum if algo=='RR' else 'N/A'}) ---{COLOR_RESET}")

        # Run scheduler
        output = run_scheduler(executable_path, algo, cpus, quantum, infile, verbose)
        if output is None:
            print(f"{COLOR_RED}>>> TEST FAILED (Scheduler execution error){COLOR_RESET}")
            continue

        # Parse results
        actual_results = parse_all_csv(output)
        if actual_results is None:
            print(f"{COLOR_RED}>>> TEST FAILED (CSV parsing error){COLOR_RESET}")
            continue

        # Compare results
        mismatches = compare_results(actual_results, expected)

        if not mismatches:
            print(f"{COLOR_GREEN}{COLOR_BOLD}>>> TEST PASSED{COLOR_RESET}")
            passed_tests += 1
        else:
            print(f"{COLOR_RED}{COLOR_BOLD}>>> TEST FAILED{COLOR_RESET}")
            print(f"{COLOR_RED}Mismatches found:{COLOR_RESET}")
            for mismatch in mismatches:
                print(f"  - {mismatch}")
                
    return passed_tests, total_tests


def main() -> None:
    """Main function to parse arguments and execute tests."""
    parser = argparse.ArgumentParser(description="Test harness for the CPU scheduler implementation.")
    parser.add_argument('--executable', default=SCHEDULER_EXECUTABLE,
                        help=f"Path to the scheduler executable (default: {SCHEDULER_EXECUTABLE})")
    parser.add_argument('--algorithm', choices=['FCFS', 'SJF', 'SRTF', 'RR'], 
                        help="Run only tests for specified algorithm")
    parser.add_argument('--test', help="Run only the specified test by name")
    parser.add_argument('--verbose', action='store_true', help="Show detailed scheduler output")
    parser.add_argument('--no-cleanup', action='store_true', help="Keep generated test files")
    args = parser.parse_args()

    executable_path = args.executable

    if not os.path.exists(executable_path):
        print(f"{COLOR_RED}Error: Executable '{executable_path}' not found.{COLOR_RESET}")
        print("Please compile the C code (e.g., gcc scheduler.c -o scheduler -lm) or provide the correct path.")
        return

    # Create all test files
    test_files = create_test_files()
    
    # Define all test cases
    all_tests = define_test_cases(test_files)
    
    # Filter tests based on command line arguments
    tests_to_run = all_tests
    if args.algorithm:
        tests_to_run = [tc for tc in all_tests if tc[1] == args.algorithm]
        if not tests_to_run:
            print(f"{COLOR_RED}No tests found for algorithm '{args.algorithm}'{COLOR_RESET}")
            return
            
    if args.test:
        tests_to_run = [tc for tc in tests_to_run if tc[0] == args.test]
        if not tests_to_run:
            print(f"{COLOR_RED}No test found with name '{args.test}'{COLOR_RESET}")
            return
    
    # Run the filtered tests
    passed, total = run_tests(executable_path, tests_to_run, args.verbose)
    
    # Print summary
    print(f"\n{COLOR_CYAN}--- Test Summary ---{COLOR_RESET}")
    summary_color = COLOR_GREEN if passed == total else COLOR_RED
    print(f"{summary_color}{COLOR_BOLD}Passed: {passed}/{total}{COLOR_RESET}")
    
    # Clean up test files
    cleanup_test_files(test_files, args.no_cleanup)


if __name__ == "__main__":
    main()