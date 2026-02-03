# CSC453Proj2
Tyler and Gal

Note: We made an enqueue_priotity3() function that handles response time better for RR by boosting the jobs that haven't run yet in the queue. If during testing RR fails, would it be possible for you to switch this line to enqueuepriority3 instead of enqueue (uncomment the line)

# Question
What happens to response time with RR as quantum lengths increase? 

When quantum lenghts increase, there becomes less context switching and it becomes closer to the FCFS algorithm (the response time increases)
