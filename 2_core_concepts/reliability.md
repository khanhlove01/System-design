A reliable system performs its intended function correctly and consistently, even in the face of faults.
While availability asks "Is the system up?", reliability asks "Is the system doing what it should?".

1. What is Reliability?
Reliability is the probability that a system will perform its intended function correctly over a given period of time, under specified conditions.

+ "Correctly" means producing the right output, not just any output.
+ "Over a given period" means reliability is measured over time, not at a single instant.
+ "Under specified conditions" means we define what normal operation looks like.

Concept	Question It Answers	Example
Availability	Is the system responding?	System returns HTTP 200
Reliability	Is the response correct?	The balance returned is accurate
Fault Tolerance	Does it keep working when components fail?	Works with one database replica down
Durability	Is data preserved despite failures?	Data survives disk failure


2. Measuring Reliability

A. Mean Time Between Failures (MTBF)

MTBF = Total Operating Time / Number of Failures
Example:
  - System ran for 10,000 hours
  - Experienced 5 failures
  - MTBF = 10,000 / 5 = 2,000 hours

B. Mean Time To Recovery (MTTR)
MTTR = Total Downtime / Number of Failures
Example:
  - 5 failures occurred
  - Total repair time: 10 hours
  - MTTR = 10 / 5 = 2 hours per failure

C. Error Rate
Error Rate = Failed Requests / Total Requests × 100%

System Type	Target Error Rate	Meaning
Critical systems	< 0.01%	1 in 10,000 requests fails
Standard systems	< 0.1%	1 in 1,000 requests fails
Tolerant systems	< 1%	1 in 100 requests fails

D. Data Correctness

Correctness = Correct Responses / Total Responses × 100%


3. Key Principles of Reliable Systems

Redundancy: means having backup components ready to take over if one part fails. This could involve multiple servers, duplicate network paths, or backup databases.

Failover Mechanisms: is the process by which a system automatically switches to a redundant or standby component when a failure is detected. This ensures continuous operation without noticeable disruption to users.

Load Balancing distributes incoming traffic across multiple servers. This not only improves performance but also prevents any single server from becoming a single point of failure.

Monitoring and Alerting: A reliable system is constantly monitored. Tools and dashboards track system health and performance, while alerting mechanisms notify engineers of issues before they escalate into major problems.

Graceful Degradation: Even when parts of the system fail, a well-designed system can still provide core functionality rather than going completely offline

1. Redundant Architectures
2. Data Replication
3. Graceful Degradation
4. Circuit Breakers
5. Idempotency