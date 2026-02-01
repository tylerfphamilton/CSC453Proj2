[1mdiff --git a/scheduler_skeleton.c b/scheduler_skeleton.c[m
[1mindex 601eb3d..369eac6 100644[m
[1m--- a/scheduler_skeleton.c[m
[1m+++ b/scheduler_skeleton.c[m
[36m@@ -582,11 +582,8 @@[m [mvoid handle_arrivals(Process *processes, int process_count, int current_time, Al[m
 void handle_rr_quantum_expiry(Process *processes, CPU *cpus, int cpu_count, int time_quantum,[m
                            ReadyQueue *ready_queue, int current_time) {[m
     // TODO: Move Round Robin processes back to the queue when their quantum expires[m
[31m-[m
[31m-[m
     // use FCFSQ[m
     // loop through the CPU list and check to see if it has been running for too[m
[31m-    // Process *current = dequeue(&FCFSQ);[m
     for (int i = 0; i < cpu_count; i++){[m
 [m
         if (cpus[i].current_process == NULL){[m
