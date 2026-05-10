import bisect
import hashlib
from typing import Optional

class ConsistentHashing:
    def __init__(self, servers: list[str], num_replicas: int = 3) -> None:
        """
        Initializes the consistent hashing ring.

        - servers: List of initial server names (e.g., ["S0", "S1", "S2"])
        - num_replicas: Number of virtual nodes per server for better load balancing
        """
        self.num_replicas: int = num_replicas  # Number of virtual nodes per server
        self.ring: dict[int, str] = {}  # Hash ring storing virtual node mappings
        self.sorted_keys: list[int] = []  # Sorted list of hash values (positions) on the ring
        self.servers: set[str] = set()  # Set of physical servers (used for tracking)

        # Add each server to the hash ring
        for server in servers:
            self.add_server(server=server)

    def _hash(self, key: str) -> int:
        """Computes a hash value for a given key using MD5."""
        encoded_key: bytes = key.encode(encoding="utf-8")
        return int(hashlib.md5(string=encoded_key, usedforsecurity=False).hexdigest(), 16)

    def add_server(self, server: str) -> None:
        """
        Adds a server to the hash ring along with its virtual nodes.

        - Each virtual node is a different hash of the server ID to distribute load.
        - The server is hashed multiple times and placed at different positions.
        """
        self.servers.add(server)
        for i in range(self.num_replicas):  # Creating multiple virtual nodes
            hash_val: int = self._hash(key=f"{server}-{i}")  # Unique hash for each virtual node
            self.ring[hash_val] = server  # Map hash to the server
            bisect.insort(self.sorted_keys, hash_val)  # Maintain a sorted list for efficient lookup

    def remove_server(self, server: str) -> None:
        """
        Removes a server and all its virtual nodes from the hash ring.
        """
        if server in self.servers:
            self.servers.remove(server)
            for i in range(self.num_replicas):
                hash_val: int = self._hash(key=f"{server}-{i}")  # Remove each virtual node's hash
                self.ring.pop(hash_val, None)  # Delete from hash ring
                self.sorted_keys.remove(hash_val)  # Remove from sorted key list

    def get_server(self, key: str) -> Optional[str]:
        """
        Finds the closest server for a given key.

        - Hash the key to get its position on the ring.
        - Move clockwise to find the nearest server.
        - If it exceeds the last node, wrap around to the first node.
        """
        if not self.ring:
            return None  # No servers available

        hash_val: int = self._hash(key=key)  # Hash the key
        index: int = bisect.bisect(self.sorted_keys, hash_val) % len(self.sorted_keys)  # Locate nearest server
        return self.ring[self.sorted_keys[index]]  # Return the assigned server

# ----------------- Usage Example -------------------

# Step 1: Initialize Consistent Hashing with servers
servers: list[str] = ["S0", "S1", "S2", "S3", "S4", "S5"]
ch: ConsistentHashing = ConsistentHashing(servers=servers)

# Step 2: Assign requests (keys) to servers
print(f"UserA is assigned to: {ch.get_server(key='UserA')}")  # Maps UserA to a server
print(f"UserB is assigned to: {ch.get_server(key='UserB')}")  # Maps UserB to a server

# Step 3: Add a new server dynamically
ch.add_server(server="S6")
print(f"UserA is now assigned to: {ch.get_server(key='UserA')}")  # Might be reassigned if affected

# Step 4: Remove a server dynamically
ch.remove_server(server="S2")
print(f"UserB is now assigned to: {ch.get_server(key='UserB')}")  # Might be reassigned if affected
