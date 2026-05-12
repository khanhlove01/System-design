Load Balancer is a system that spreads incoming network traffic across multiple backend servers (often called “worker nodes” or “application servers”)

=> ensures that no single server becomes a bottleneck

1. Why Do We Need a Load Balancer?
Scalability: As traffic grows, you can add more servers behind the load balancer without redesigning your entire architecture.

High Availability: If one server goes offline or crashes, the load balancer automatically reroutes traffic to other healthy servers.

Performance Optimization: Balancing load prevents certain servers from overworking while others remain underutilized.

Maintainability: You can perform maintenance on individual servers without taking your entire application down.

2. Types of Load Balancers

Layer 4 vs. Layer 7

+ Layer 4 (Transport Layer): Distributes traffic based on network information like IP address and port. It doesn’t inspect the application-layer data (HTTP, HTTPS headers, etc.).

=> Layer 4 = Transport Layer, chủ yếu nhìn vào thông tin mạng như:
=> 

Source IP
Source port
Destination IP
Destination port
Protocol: TCP hoặc UDP

Nó không hiểu nội dung HTTP bên trong request.
=> Ví dụ request:
GET /api/users HTTP/1.1
Host: example.com
Cookie: user_id=123

Layer 4 load balancer không đọc các phần như:

/api/users
Host
Cookie
Header
Body

=> Nó chỉ thấy kiểu:
Client IP: 14.160.x.x
Client Port: 51512
Server IP: 10.0.1.10
Server Port: 443
Protocol: TCP

Sau đó nó quyết định chuyển connection tới backend nào.
=> Client -> L4 Load Balancer -> Backend A

(round robin, least connections, source IP hash)

+ Layer 7 (Application Layer): Can make distribution decisions based on HTTP headers, cookies, URL path, etc. This is useful for advanced routing and application-aware features.

=> Layer 7 = Application Layer, nghĩa là load balancer hiểu protocol ứng dụng, thường là HTTP/HTTPS.

HTTP method: GET, POST
URL path: /api/users
Host: api.example.com
Headers
Cookies
Query params
Content type

GET /api/users HTTP/1.1
Host: api.example.com
Cookie: plan=premium

=> Layer 7 load balancer có thể quyết định:

Nếu path bắt đầu bằng /api/users -> User Service
Nếu path bắt đầu bằng /api/orders -> Order Service
Nếu cookie plan=premium -> Premium Backend
Nếu host là admin.example.com -> Admin Service

Feature	Layer 4 LB	Layer 7 LB
Nhìn vào	IP, port, TCP/UDP	HTTP headers, path, cookies, method
Hiểu HTTP?	Không	Có
Route theo /api/users?	Không	Có
Route theo port?	Có	Có
Tốc độ	Nhanh hơn	Linh hoạt hơn nhưng overhead cao hơn
Phù hợp cho	TCP/UDP generic traffic	Web/API traffic
Ví dụ	AWS NLB, LVS	Nginx, Envoy, AWS ALB, API Gateway

3. How Load Balancing Works

Step 1: Traffic Reception (All incoming requests arrive at the load balancer’s public IP or domain (e.g., www.myapp.com).)

Step 2: Decision Logic (Routing Algorithm)

+ Round Robin: Requests are distributed sequentially to each server in a loop.
+ Weighted Round Robin: Each server is assigned a weight (priority). Servers with higher weights receive proportionally more requests.
+ Least Connections: The request goes to the server with the fewest active connections.
+ IP Hash: The load balancer uses a hash of the client’s IP to always route them to the same server (useful for sticky sessions).
+ Random: Select a server randomly (sometimes used for quick prototypes or specialized cases).

Step 3: Server Health Checks

LB usually has an internal mechanism to periodically check if servers are alive
=> (e.g., by sending a heartbeat request like an HTTP GET /health).

Step 4: Response Handling

Once a request is forwarded to a healthy server, the server processes it and returns the response to the load balancer, which then returns it to the client.

4. Key Features
+ SSL/TLS Termination: Offloads cryptographic operations from the servers. The load balancer decrypts incoming SSL traffic and sends plain HTTP traffic to backend servers, reducing their CPU load.

+ Sticky Sessions (Session Persistence): Sends the same client to the same backend server for session consistency.

+ Auto Scaling: New servers can be added or removed automatically based on traffic.

+ Caching and Compression: Can cache responses or compress data to reduce latency and bandwidth.

Security Features: May include WAF, DDoS protection, rate limiting, and traffic filtering.

5. Example Use Cases
E-Commerce Website: Distributes traffic during peak events and helps scale by adding more servers.

Video Streaming Platform: Balances high viewer traffic to keep streaming smooth.

API Gateway: Modern microservices often place a load balancer or reverse proxy in front of internal services to route API calls based on route paths or hostnames.

6. Conclusion
By using load balancers effectively, you can:

Scale out your infrastructure seamlessly.
Enhance availability and fault tolerance.
Improve performance by offloading tasks like SSL termination and caching.
Maintain your systems more easily, taking servers offline without impacting the entire application.