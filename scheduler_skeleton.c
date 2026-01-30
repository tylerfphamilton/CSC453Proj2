/**
 * CPU Scheduler Simulator
 *
 * Simulates multiple CPU scheduling algorithms:
 * - First-Come, First-Served (FCFS)
 * - Round Robin (RR)
 * - Shortest Remaining Time First (SRTF)
 * - Shortest Job First (SJF)
 * 
 * Features:
 * - Multiple CPU support
 * - Visual timeline of execution
 * - Process and CPU statistics
 * - CSV output for automated testing
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <limits.h>

/************************* CONSTANTS & DEFINITIONS *************************/

// Scheduling algorithm identifiers
typedef enum {
    FCFS = 0,  // First-Come, First-Served
    RR   = 1,  // Round Robin
    SRTF = 2,  // Shortest Remaining Time First (preemptive)
    SJF  = 3   // Shortest Job First (non-preemptive)
} Algorithm;

// Process states
typedef enum {
    WAITING    = 0,  // Ready to run but not yet scheduled or arrived
    RUNNING    = 1,  // Currently executing on a CPU
    COMPLETED  = 2,  // Finished execution
    READY      = 3   // In the ready queue (specifically for RR)
} ProcessState;

// Configuration constants
#define DEFAULT_TIME_QUANTUM 2
#define MAX_PROCESSES 500
#define INITIAL_TIMELINE_CAPACITY 1000
#define MAX_LINE_LENGTH 256

// Display settings
#define TIMELINE_WIDTH 80
#define TIME_UNIT_WIDTH 5

// Color codes for visualization
#define COLOR_RESET  "\033[0m"
#define COLOR_BOLD   "\033[1m"
#define COLOR_RED    "\033[31m"
#define COLOR_GREEN  "\033[32m"
#define COLOR_YELLOW "\033[33m"
#define COLOR_BLUE   "\033[34m"
#define COLOR_MAGENTA "\033[35m"
#define COLOR_CYAN   "\033[36m"
#define COLOR_WHITE  "\033[37m"

const char *PROCESS_COLORS[] = {
    COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE,
    COLOR_MAGENTA, COLOR_CYAN, COLOR_WHITE
};
#define NUM_PROCESS_COLORS (sizeof(PROCESS_COLORS) / sizeof(PROCESS_COLORS[0]))

/************************* TYPE DEFINITIONS *************************/

/**
 * Process data structure containing all information about a process
 */
typedef struct {
    int pid;              // Process ID
    int arrival_time;     // Time when process becomes available
    int burst_time;       // Total CPU time required
    int priority;         // Priority (higher value = higher priority)
    int remaining_time;   // Remaining CPU time needed
    ProcessState state;   // Current state (WAITING, RUNNING, etc.)
    int start_time;       // When process first started (-1 if not started)
    int finish_time;      // When process completed (-1 if not finished)
    int waiting_time;     // Total time spent waiting
    int quantum_used;     // Time units used in current quantum (for RR)
    int response_time;    // Time between arrival and first execution
} Process;

/**
 * CPU data structure representing a processor
 */
typedef struct {
    int id;               // CPU identifier
    Process *current_process; // Process currently running (NULL if idle)
    int idle_time;        // Total time CPU was idle
    int busy_time;        // Total time CPU was busy
} CPU;

/**
 * Simple circular queue for RR scheduling
 */
typedef struct {
    int process_indices[MAX_PROCESSES]; // Array of process indices
    int front;            // Index of front element
    int rear;             // Index of rear element
    int size;             // Current queue size
} ReadyQueue;



/************************* FUNCTION PROTOTYPES *************************/

// File operations
void load_processes(const char *filename, Process **processes_ptr, int *count);

// Scheduling functions
void simulate(Process *processes, int process_count, int cpu_count, Algorithm algorithm, int time_quantum);
void handle_arrivals(Process *processes, int process_count, int current_time, Algorithm algorithm, 
                    int *arrived_indices, int *arrival_count);
void handle_rr_quantum_expiry(Process *processes, CPU *cpus, int cpu_count, int time_quantum, 
                             ReadyQueue *ready_queue, int current_time);
void handle_srtf_preemption(Process *processes, int process_count, CPU *cpus, int cpu_count, int current_time);
void assign_processes_to_idle_cpus(Process *processes, int process_count, CPU *cpus, int cpu_count, 
                                 Algorithm algorithm, ReadyQueue *ready_queue, int current_time);
void execute_processes(Process *processes, int process_count, CPU *cpus, int cpu_count, 
                      int current_time, int *completed_count);
void update_waiting_times(Process *processes, int process_count, int current_time);

// Output and visualization
void print_results(Process *processes, int process_count, CPU *cpus, int cpu_count, int **timeline, int total_time);
void print_timeline(int **timeline, int total_time, Process *processes, int process_count, int cpu_count);
void print_process_stats(Process *processes, int process_count);
void print_cpu_stats(CPU *cpus, int cpu_count);
void print_average_stats(Process *processes, int process_count);
void print_csv_output(Process *processes, int process_count, CPU *cpus, int cpu_count);

// Queue operations
void init_queue(ReadyQueue *q);
void enqueue(ReadyQueue *q, int process_idx);
int dequeue(ReadyQueue *q);

// Timeline management
void init_timeline(int ***timeline_ptr, int capacity, int cpu_count);
void expand_timeline(int ***timeline_ptr, int *capacity_ptr, int new_capacity, int cpu_count);
void cleanup_timeline(int **timeline, int capacity);

// Helper functions
const char* get_color_for_pid(int pid);
const char* algorithm_name(Algorithm algorithm);
void parse_arguments(int argc, char *argv[], Algorithm *algorithm, int *cpu_count, 
                    int *time_quantum, char **input_file);


// GLOBAL QUEUE
ReadyQueue FCFSQ;
/************************* QUEUE OPERATIONS *************************/

/**
 * Initialize a ready queue
 */
void init_queue(ReadyQueue *q) {
    q->front = 0;
    q->rear = -1;
    q->size = 0;
}

/**
 * Add a process index to the ready queue
 */

 static void print_queue(const ReadyQueue *q) {
    printf("Q front=%d rear=%d size=%d: ", q->front, q->rear, q->size);
    for (int k = 0; k < q->size; k++) {
        int idx = (q->front + k) % MAX_PROCESSES;
        printf("%d ", q->process_indices[idx]);
    }
    printf("\n");
}


void enqueue(ReadyQueue *q, int process_idx) {
    if (q->size >= MAX_PROCESSES) {
        fprintf(stderr, "Error: Ready queue overflow!\n");
        return;
    }
    q->rear = (q->rear + 1) % MAX_PROCESSES;
    q->process_indices[q->rear] = process_idx;
    q->size++;
    //print_queue(q);
}

void enqueue_priority(ReadyQueue *q, int process_idx , Process *processes){
    if (q->size >= MAX_PROCESSES) {
        fprintf(stderr, "Error: Ready queue overflow!\n");
        return;
    }

    if (q->rear == -1){
        enqueue(q , process_idx);
        return;
    }

    int cur = q->front; 
    int new_time = processes[process_idx].remaining_time;
    int new_priority = processes[process_idx].priority; 

    // scan queue from front to rear
    while (cur != (q->rear + 1) % MAX_PROCESSES){
        int cur_time = processes[q->process_indices[cur]].remaining_time;
        int cur_priority = processes[q->process_indices[cur]].priority;

        if (new_time < cur_time || 
           (new_time == cur_time && new_priority > cur_priority)){
            break;
        }
        cur = (cur + 1) % MAX_PROCESSES;
    }

    if (cur == (q->rear + 1) % MAX_PROCESSES){  
        enqueue(q , process_idx);
        return;
    }

    q->rear = (q->rear + 1) % MAX_PROCESSES;    

    int temp = q->process_indices[cur];
    q->process_indices[cur] = process_idx;

    int temp2;
    int nextcur = (cur + 1) % MAX_PROCESSES;

    while (cur != q->rear){                      // FIX: clearer stop condition
        temp2 = q->process_indices[nextcur];
        q->process_indices[nextcur] = temp;
        temp = temp2;

        cur = nextcur;                        
        nextcur = (cur + 1) % MAX_PROCESSES;  
    }

    q->size++;
    //print_queue(q);
}


/**
 * Remove and return the next process index from the ready queue
 * Returns -1 if queue is empty
 */
int dequeue(ReadyQueue *q) {
    if (q->size <= 0) return -1; // Queue empty
    int process_idx = q->process_indices[q->front];
    q->front = (q->front + 1) % MAX_PROCESSES;
    q->size--;
    return process_idx;
}

/************************* TIMELINE MANAGEMENT *************************/

/**
 * Initialize the simulation timeline data structure
 */
void init_timeline(int ***timeline_ptr, int capacity, int cpu_count) {
    *timeline_ptr = (int **)malloc(capacity * sizeof(int *));
    if (!(*timeline_ptr)) {
        perror("Failed to allocate timeline");
        exit(EXIT_FAILURE);
    }
    
    for (int t = 0; t < capacity; t++) {
        (*timeline_ptr)[t] = (int *)malloc(cpu_count * sizeof(int));
        if (!(*timeline_ptr)[t]) {
            perror("Failed to allocate timeline row");
            // Clean up already allocated rows
            for (int k = 0; k < t; k++) free((*timeline_ptr)[k]);
            free(*timeline_ptr);
            exit(EXIT_FAILURE);
        }
        for (int c = 0; c < cpu_count; c++) {
            (*timeline_ptr)[t][c] = -1; // -1 indicates idle
        }
    }
}

/**
 * Expand timeline capacity when needed
 */
void expand_timeline(int ***timeline_ptr, int *capacity_ptr, int new_capacity, int cpu_count) {
    int **temp = (int **)realloc(*timeline_ptr, new_capacity * sizeof(int *));
    if (!temp) {
        perror("Failed to expand timeline");
        exit(EXIT_FAILURE);
    }
    *timeline_ptr = temp;

    for (int t = *capacity_ptr; t < new_capacity; t++) {
        (*timeline_ptr)[t] = (int *)malloc(cpu_count * sizeof(int));
        if (!(*timeline_ptr)[t]) {
            perror("Failed to allocate new timeline row during expansion");
            exit(EXIT_FAILURE);
        }
        for (int c = 0; c < cpu_count; c++) {
            (*timeline_ptr)[t][c] = -1;
        }
    }
    *capacity_ptr = new_capacity;
}

/**
 * Clean up the timeline data structure
 */
void cleanup_timeline(int **timeline, int capacity) {
    if (timeline) {
        for (int t = 0; t < capacity; t++) {
            free(timeline[t]);
        }
        free(timeline);
    }
}

/************************* HELPER FUNCTIONS *************************/

/**
 * Get a color code for a process ID for colorized output
 */
const char* get_color_for_pid(int pid) {
    if (pid < 0) return COLOR_RESET; // Idle
    return PROCESS_COLORS[pid % NUM_PROCESS_COLORS];
}

/**
 * Get the algorithm name as a string
 */
const char* algorithm_name(Algorithm algorithm) {
    switch (algorithm) {
        case FCFS: return "First-Come, First-Served";
        case RR:   return "Round Robin";
        case SRTF: return "Shortest Remaining Time First";
        case SJF:  return "Shortest Job First";
        default:   return "Unknown Algorithm";
    }
}

/**
 * Parse command line arguments
 */
void parse_arguments(int argc, char *argv[], Algorithm *algorithm, int *cpu_count, 
                    int *time_quantum, char **input_file) {
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-a") == 0 && i + 1 < argc) {
            i++;
            if (strcmp(argv[i], "FCFS") == 0) *algorithm = FCFS;
            else if (strcmp(argv[i], "RR") == 0) *algorithm = RR;
            else if (strcmp(argv[i], "SRTF") == 0) *algorithm = SRTF;
            else if (strcmp(argv[i], "SJF") == 0) *algorithm = SJF;
            // Default is FCFS
        } else if (strcmp(argv[i], "-c") == 0 && i + 1 < argc) {
            *cpu_count = atoi(argv[++i]);
            if (*cpu_count <= 0) *cpu_count = 1; // Ensure at least 1 CPU
        } else if (strcmp(argv[i], "-q") == 0 && i + 1 < argc) {
            *time_quantum = atoi(argv[++i]);
            if (*time_quantum <= 0) *time_quantum = DEFAULT_TIME_QUANTUM;
        } else if (strcmp(argv[i], "-f") == 0 && i + 1 < argc) {
            *input_file = argv[++i];
        } else {
            fprintf(stderr, "Usage: %s -f <file> [-a <FCFS|RR|SRTF|SJF>] [-c <cpus>] [-q <quantum>]\n", argv[0]);
            exit(EXIT_FAILURE);
        }
    }

    if (!(*input_file)) {
        fprintf(stderr, "Error: Input file required. Use -f <filename>\n");
        exit(EXIT_FAILURE);
    }
}



/************************* PROCESS LOADING *************************/

/**
 * Load processes from a file
 * 
 * Expected format:
 * <PID> <arrival_time> <burst_time> [priority]
 * 
 * Lines starting with # are treated as comments
 */
void load_processes(const char *filename, Process **processes_ptr, int *count) {
    FILE *file = fopen(filename, "r");
    if (!file) {
        perror("Error opening process file");
        exit(EXIT_FAILURE);
    }

    // Count valid lines first
    int process_count = 0;
    char line[MAX_LINE_LENGTH];
    while (fgets(line, sizeof(line), file)) {
        if (line[0] != '#' && line[0] != '\n' && strspn(line, " \t\n\r") != strlen(line)) {
            int pid, arrival, burst;
            if (sscanf(line, "%d %d %d", &pid, &arrival, &burst) == 3) {
                process_count++;
            }
        }
    }

    if (process_count == 0) {
        *processes_ptr = NULL;
        *count = 0;
        fclose(file);
        printf("Warning: No valid processes found in %s\n", filename);
        return;
    }

    // Allocate memory
    *processes_ptr = (Process *)malloc(process_count * sizeof(Process));
    if (!(*processes_ptr)) {
        perror("Memory allocation failed for processes");
        fclose(file);
        exit(EXIT_FAILURE);
    }

    // Read process data
    rewind(file);
    int i = 0;
    while (fgets(line, sizeof(line), file) && i < process_count) {
        if (line[0] == '#' || line[0] == '\n' || strspn(line, " \t\n\r") == strlen(line)) continue;

        int pid, arrival, burst, priority = 0; // Default priority
        int items_read = sscanf(line, "%d %d %d %d", &pid, &arrival, &burst, &priority);

        if (items_read >= 3) { // Need at least PID, arrival, burst
            Process *p = &(*processes_ptr)[i];
            p->pid = pid;
            p->arrival_time = arrival;
            p->burst_time = burst;
            p->priority = (items_read == 4) ? priority : 0; // Assign priority if read
            p->remaining_time = burst;
            p->state = WAITING;
            p->start_time = -1;
            p->finish_time = -1;
            p->waiting_time = 0;
            p->quantum_used = 0;
            p->response_time = -1;
            i++;
        }
    }
    fclose(file);

    *count = i; // Actual number of processes successfully read
    printf("Loaded %d processes from %s\n", *count, filename);
}

/************************* SIMULATION COMPONENTS *************************/

/**
 * Handle process arrivals at the current time
 */
void handle_arrivals(Process *processes, int process_count, int current_time, Algorithm algorithm,
                   int *arrived_indices, int *arrival_count) {
    // TODO: Find and record processes that have arrived at the current time
    // Remember to handle state transitions appropriately for each algorithm type
    // FCFS = 0, RR = 1, SRTF (preemptive) = 2, SJF (non-preemptive) = 3
    if (processes == NULL || arrived_indices == NULL || arrival_count == NULL){
        perror("There was a variable that was NULL in the handle_arrivals function");
        return;
    }

    // need to loop through the current processes, check to see if the time matches with the current time and check to see if the state is in WAITING
    for (int i = 0; i < process_count; i++){

        if (processes[i].arrival_time == current_time){

            if (*arrival_count < MAX_PROCESSES){  
                processes[i].state = READY;         
                arrived_indices[*arrival_count] = i;
                processes[i].quantum_used = 0;          // for RR
                (*arrival_count)++; 
            }
        }
    }
    
    // need to ask what to do here (how do I add to queue and the other data structures. If not doing this, what do I do in this part?)
    for (int idx = 0; idx < *arrival_count; idx++){

        // FCFS
        if (algorithm == 0){
            //add the index of the process (in processes, in the FCSFQ)
            enqueue(&FCFSQ , arrived_indices[idx]);
            // need to add it to a queue somehow (there is only a rr queue)
            

        }
        // Not sure if we need RR enqueuing because it does it in simulate because
        // // RR
        // else if (algorithm == 1){

            

        // }

        else if (algorithm == 2){

            

        }
        else if (algorithm == 3){ //SJF
            enqueue_priority(&FCFSQ , arrived_indices[idx] , processes);


        }
        else {
            // algorithm number is incorrect (do something)
        }
        // need to increment the number of arrival_cont and add it to the arrival_indeices (at the end)

            
    }
}

/**
 * Handle quantum expiration for Round Robin scheduling
 */
void handle_rr_quantum_expiry(Process *processes, CPU *cpus, int cpu_count, int time_quantum,
                           ReadyQueue *ready_queue, int current_time) {
    // TODO: Move Round Robin processes back to the queue when their quantum expires


    // use FCFSQ
    // loop through the CPU list and check to see if it has been running for too
    // Process *current = dequeue(&FCFSQ);
    for (int i = 0; i < cpu_count; i++){

        if (cpus[i].current_process == NULL){
            continue;
        }

        // if there is still time left and if it is still running
        if (cpus[i].current_process->remaining_time > 0 && cpus[i].current_process->state == RUNNING){

            // get the current process
            Process *curr = cpus[i].current_process;
            
            // if the quantum used is greater than the max quantum time, put it to the back of the list
            if (curr->quantum_used >= time_quantum){

                // resetting time quantum
                curr->quantum_used = 0;
                curr->state = READY;
                int curr_idx = curr - processes;
                enqueue(&FCFSQ, curr_idx);
                cpus[i].current_process = NULL;   
            }
        }
    }
    // (void)current_time; // Explicitly mark as unused
}

/**
 * Implement preemptive scheduling for SRTF
 */
void handle_srtf_preemption(Process *processes, int process_count, CPU *cpus, int cpu_count, int current_time) {
    // TODO: Implement preemption logic for SRTF: replace running processes if a ready process is shorter
    // Consider priority as a tiebreaker when remaining times are equal
    if (processes == NULL || cpus == NULL){
        perror("There is an issue at the beginning of handle_srtf_preemption()");
    }

    
}

/**
 * Assign processes to idle CPUs based on the current scheduling algorithm
 */
void assign_processes_to_idle_cpus(Process *processes, int process_count, CPU *cpus, int cpu_count,
                                Algorithm algorithm, ReadyQueue *ready_queue, int current_time) {
    // TODO: Select and assign processes to idle CPUs according to the chosen algorithm
    // Each algorithm has different process selection criteria
    // Be careful not to assign the same process to multiple CPUs

    for (int c = 0; c < cpu_count; c++) {
        if (cpus[c].current_process != NULL) continue; //if null, don't skip

        int idx = dequeue(&FCFSQ);

        if (idx == -1) break;

        Process *p = &processes[idx];

        if (p->state == COMPLETED || p->arrival_time > current_time) {
            c--;
            continue;
        }

        cpus[c].current_process = p;
        p->state = RUNNING;

        if (p->start_time == -1) {
            p->start_time = current_time;
            p->response_time = current_time - p->arrival_time;
        }

        p->quantum_used = 0;
    }

}

/**
 * Update waiting times for all waiting processes
 */
void update_waiting_times(Process *processes, int process_count, int current_time) {
    // TODO: Increment waiting_time for processes that have arrived but are not running
    for (int w = 0 ; w < process_count; w++) {
        if (processes[w].state == WAITING && processes[w].arrival_time <= current_time) {
            processes[w].waiting_time++;
        }
    }
}

/**
 * Execute processes on CPUs for the current time step
 */
void execute_processes(Process *processes, int process_count, CPU *cpus, int cpu_count,
                     int current_time, int *completed_count) {
    // TODO: Execute one time unit of each running process and track CPU idle/busy time
    for (int c = 0 ; c < cpu_count ; c++){ 
    // check each CPU. If something is mounted, do work (increase busy time, decrease remaining time)
    //if nothing is running increase idle time. Throw away tasks that finished.
        if (cpus[c].current_process != NULL) {
            Process *p = cpus[c].current_process;
            p->remaining_time--;
            cpus[c].busy_time++;
            p->quantum_used++;

            if (p->remaining_time <= 0) {
                p->finish_time = current_time + 1; // +1 because time is incremented after execution
                p->state = COMPLETED;
                cpus[c].current_process = NULL;
                (*completed_count)++;
            }
        } else {
            cpus[c].idle_time++;
        }
    }
    (void)processes;
    (void)process_count;
}

/************************* MAIN SIMULATION *************************/

/**
 * Run the entire CPU scheduling simulation
 */
void simulate(Process *processes, int process_count, int cpu_count, Algorithm algorithm, int time_quantum) {
    // Initialize simulation components
    ReadyQueue ready_queue_rr; 
    init_queue(&ready_queue_rr);

    CPU *cpus = (CPU *)calloc(cpu_count, sizeof(CPU)); 
    if (!cpus) {
        perror("Failed to allocate CPUs");
        exit(EXIT_FAILURE);
    }
    for (int i = 0; i < cpu_count; i++) cpus[i].id = i;

    int timeline_capacity = INITIAL_TIMELINE_CAPACITY;
    int **timeline = NULL;
    init_timeline(&timeline, timeline_capacity, cpu_count);

    int current_time = 0;
    int completed_count = 0;
    
    // Display simulation header
    printf("\nStarting simulation with %s on %d CPU(s)%s\n", 
           algorithm_name(algorithm),
           cpu_count, 
           algorithm == RR ? ", Quantum=" : "");
    if (algorithm == RR) printf("%d", time_quantum);
    printf("\n");
    int bruh = 0;
    // Main Simulation Loop
    while (completed_count < process_count) {
        // TODO: Complete the simulation loop
        // The framework is provided, but several function calls need implementation

        // Handle new process arrivals
        int arrived_indices[MAX_PROCESSES];
        int arrival_count = 0;
        handle_arrivals(processes, process_count, current_time, algorithm, arrived_indices, &arrival_count);
        //printf("OOOGAGAA");
        //printf("current arrivals: %d\n", arrival_count);
        //printf("current time: %d\n", current_time);

        // Enqueue newly arrived processes for Round Robin
        if (algorithm == RR) {
            for (int i = 0; i < arrival_count; i++) {
                // enqueue(&ready_queue_rr, arrived_indices[i]);
                enqueue(&FCFSQ, arrived_indices[i]);
            }
            handle_rr_quantum_expiry(processes, cpus, cpu_count, time_quantum, &ready_queue_rr, current_time);
        }

        // Handle SRTF preemption
        if (algorithm == SRTF) {
            handle_srtf_preemption(processes, process_count, cpus, cpu_count, current_time);
        }

        // Assign processes to idle CPUs
        assign_processes_to_idle_cpus(processes, process_count, cpus, cpu_count, algorithm,
                                   &ready_queue_rr, current_time);
        
        //printf("cpu is currently doing: %d ", cpus[0].current_process);

        // Update timeline
        if (current_time >= timeline_capacity) {
            expand_timeline(&timeline, &timeline_capacity, timeline_capacity * 2, cpu_count);
        }
        for (int c = 0; c < cpu_count; c++) {
            timeline[current_time][c] = (cpus[c].current_process != NULL) ? cpus[c].current_process->pid : -1;
        }

        // Update waiting times for processes
        update_waiting_times(processes, process_count, current_time); // I think I finished this

        // Execute processes on CPUs
        execute_processes(processes, process_count, cpus, cpu_count, current_time, &completed_count);
        // I think this is also done

        // Advance time
        current_time++;

        // Safety break to prevent infinite loops
        if (current_time > timeline_capacity * 5 && completed_count < process_count) {
            fprintf(stderr, "Warning: Simulation exceeded maximum expected time. Aborting.\n");
            break;
        }
        bruh ++;
        if (bruh > 100){
            break;
        }
    }

    int total_time = current_time; // Record total simulation time
    print_results(processes, process_count, cpus, cpu_count, timeline, total_time);

    // Cleanup
    cleanup_timeline(timeline, timeline_capacity);
    free(cpus);
}

/************************* RESULTS DISPLAY *************************/

/**
 * Print the execution timeline visualization
 */
void print_timeline(int **timeline, int total_time, Process *processes, int process_count, int cpu_count) {
    printf("\nExecution Timeline:\n");
    int time_units_per_line = (TIMELINE_WIDTH - 5) / TIME_UNIT_WIDTH;
    if (time_units_per_line <= 0) time_units_per_line = 1; // Ensure at least 1 unit per line
    int time_segments = (total_time + time_units_per_line - 1) / time_units_per_line;

    // Print color key
    printf("\nColor Key:\n");
    for (int i = 0; i < process_count; i++) {
        printf("%sPID %-2d%s ", get_color_for_pid(processes[i].pid), processes[i].pid, COLOR_RESET);
        if ((i + 1) % 8 == 0 && i + 1 < process_count) printf("\n");
    }
    printf("\n");

    // Print timeline in segments
    for (int segment = 0; segment < time_segments; segment++) {
        int start_t = segment * time_units_per_line;
        int end_t = start_t + time_units_per_line;
        if (end_t > total_time) end_t = total_time;

        printf("\nTime %d to %d:\n", start_t, end_t - 1);

        // Time markers
        printf("Time: ");
        for (int t = start_t; t < end_t; t++) {
            printf("%-5d", t); // Print time marker for each unit
        }
        printf("\n");

        // CPU timelines
        for (int c = 0; c < cpu_count; c++) {
            printf("CPU%-2d ", c);
            for (int t = start_t; t < end_t; t++) {
                int pid = timeline[t][c];
                if (pid == -1) {
                    printf("%-*s", TIME_UNIT_WIDTH, "."); // Idle marker
                } else {
                    printf("%s%-*d%s", get_color_for_pid(pid), TIME_UNIT_WIDTH, pid, COLOR_RESET);
                }
            }
            printf("\n");
        }
    }
}

/**
 * Print detailed process statistics
 */
void print_process_stats(Process *processes, int process_count) {
    printf("\nProcess Statistics:\n");
    printf("%-6s %-7s %-7s %-7s %-7s %-7s %-7s %-7s\n",
           "PID", "Arrival", "Burst", "Start", "Finish", "Turn.", "Waiting", "Resp.");
    printf("----------------------------------------------------------------\n");

    for (int i = 0; i < process_count; i++) {
        Process *p = &processes[i];
        if (p->finish_time != -1) { // Only calculate for completed processes
            int turnaround = p->finish_time - p->arrival_time;
            int waiting = turnaround - p->burst_time;
            if (waiting < 0) waiting = 0; // Cannot be negative

            printf("%-6d %-7d %-7d %-7d %-7d %-7d %-7d %-7d\n",
                   p->pid, p->arrival_time, p->burst_time,
                   p->start_time, p->finish_time, turnaround, waiting, p->response_time);
        } else {
            printf("%-6d %-7d %-7d %-7s %-7s %-7s %-7s %-7s\n",
                   p->pid, p->arrival_time, p->burst_time,
                   (p->start_time == -1 ? "N/A" : "-"), "N/A", "N/A", "N/A",
                   (p->response_time == -1 ? "N/A" : "-"));
        }
    }
    printf("----------------------------------------------------------------\n");
}

/**
 * Print CPU usage statistics
 */
void print_cpu_stats(CPU *cpus, int cpu_count) {
    printf("\nCPU Statistics:\n");
    printf("%-6s %-9s %-9s %-12s\n", "CPU ID", "Busy Time", "Idle Time", "Utilization");
    printf("------------------------------------------\n");
    for (int i = 0; i < cpu_count; i++) {
        double utilization = 0.0;
        int cpu_total_time = cpus[i].busy_time + cpus[i].idle_time;
        if (cpu_total_time > 0) {
            utilization = 100.0 * cpus[i].busy_time / cpu_total_time;
        }
        printf("%-6d %-9d %-9d %-11.2f%%\n", cpus[i].id, cpus[i].busy_time, cpus[i].idle_time, utilization);
    }
    printf("------------------------------------------\n");
}

/**
 * Print average performance metrics
 */
void print_average_stats(Process *processes, int process_count) {
    double total_turnaround = 0.0, total_waiting = 0.0, total_response = 0.0;
    int valid_stats_count = 0;

    for (int i = 0; i < process_count; i++) {
        Process *p = &processes[i];
        if (p->finish_time != -1) { // Only calculate for completed processes
            int turnaround = p->finish_time - p->arrival_time;
            int waiting = turnaround - p->burst_time;
            if (waiting < 0) waiting = 0;

            total_turnaround += turnaround;
            total_waiting += waiting;
            total_response += p->response_time;
            valid_stats_count++;
        }
    }

    if (valid_stats_count > 0) {
        printf("\nAverage Statistics (for %d completed processes):\n", valid_stats_count);
        printf("  Average Turnaround Time: %.2f\n", total_turnaround / valid_stats_count);
        printf("  Average Waiting Time:    %.2f\n", total_waiting / valid_stats_count);
        printf("  Average Response Time:   %.2f\n", total_response / valid_stats_count);
    } else {
        printf("\nNo processes completed. Cannot calculate average statistics.\n");
    }
}

/**
 * Generate CSV output for automated testing
 */
void print_csv_output(Process *processes, int process_count, CPU *cpus, int cpu_count) {
    printf("\n\n--- CSV Output ---\n");
    
    // Process stats CSV
    printf("\nProcess Stats (CSV):\n");
    printf("PID,Arrival,Burst,Priority,Start,Finish,Turnaround,Waiting,Response\n");
    for (int i = 0; i < process_count; i++) {
        Process *p = &processes[i];
        if (p->finish_time != -1) {
            int turnaround = p->finish_time - p->arrival_time;
            int waiting = turnaround - p->burst_time;
            if (waiting < 0) waiting = 0;
            printf("%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
                   p->pid, p->arrival_time, p->burst_time, p->priority,
                   p->start_time, p->finish_time, turnaround, waiting, p->response_time);
        } else {
             printf("%d,%d,%d,%d,%s,%s,%s,%s,%s\n",
                   p->pid, p->arrival_time, p->burst_time, p->priority,
                   "N/A", "N/A", "N/A", "N/A", "N/A");
        }
    }

    // CPU stats CSV
    printf("\nCPU Stats (CSV):\n");
    printf("CPU_ID,BusyTime,IdleTime,Utilization%%\n");
    for (int i = 0; i < cpu_count; i++) {
        double utilization = 0.0;
        int cpu_total_time = cpus[i].busy_time + cpus[i].idle_time;
        if (cpu_total_time > 0) {
            utilization = 100.0 * cpus[i].busy_time / cpu_total_time;
        }
        printf("%d,%d,%d,%.2f\n", cpus[i].id, cpus[i].busy_time, cpus[i].idle_time, utilization);
    }

    // Average stats CSV
    double total_turnaround = 0.0, total_waiting = 0.0, total_response = 0.0;
    int valid_stats_count = 0;
    for (int i = 0; i < process_count; i++) {
        Process *p = &processes[i];
        if (p->finish_time != -1) {
            int turnaround = p->finish_time - p->arrival_time;
            int waiting = turnaround - p->burst_time;
            if (waiting < 0) waiting = 0;
            
            total_turnaround += turnaround;
            total_waiting += waiting;
            total_response += p->response_time;
            valid_stats_count++;
        }
    }

    printf("\nAverage Stats (CSV):\n");
    printf("AvgTurnaround,AvgWaiting,AvgResponse\n");
    if (valid_stats_count > 0) {
        printf("%.2f,%.2f,%.2f\n",
               total_turnaround / valid_stats_count,
               total_waiting / valid_stats_count,
               total_response / valid_stats_count);
    } else {
        printf("N/A,N/A,N/A\n");
    }
    printf("--- End CSV Output ---\n");
}

/**
 * Display all simulation results
 */
void print_results(Process *processes, int process_count, CPU *cpus, int cpu_count, int **timeline, int total_time) {
    printf("\n--- Simulation Results ---\n");

    // Print visual timeline
    print_timeline(timeline, total_time, processes, process_count, cpu_count);
    
    // Print detailed statistics
    print_process_stats(processes, process_count);
    print_cpu_stats(cpus, cpu_count);
    print_average_stats(processes, process_count);
    
    // Print CSV output for automated testing
    print_csv_output(processes, process_count, cpus, cpu_count);
}

/************************* MAIN FUNCTION *************************/

int main(int argc, char *argv[]) {
    init_queue(&FCFSQ);
    Algorithm algorithm = FCFS;
    int cpu_count = 1;
    int time_quantum = DEFAULT_TIME_QUANTUM;
    char *input_file = NULL;

    // Parse command line arguments
    parse_arguments(argc, argv, &algorithm, &cpu_count, &time_quantum, &input_file);

    // Load processes
    Process *processes = NULL;
    int process_count = 0;
    load_processes(input_file, &processes, &process_count);

    // Run simulation if processes were loaded successfully
    if (process_count > 0) {
        simulate(processes, process_count, cpu_count, algorithm, time_quantum);
    } else {
        printf("No processes loaded or simulation not possible.\n");
    }

    // Clean up
    free(processes);
    return EXIT_SUCCESS;
}
