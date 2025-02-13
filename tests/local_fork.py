"""
Local chain fork for testing
"""


import socket
import time
from dataclasses import dataclass
from typing import Optional

import requests
from docker import DockerClient
from docker.models.containers import Container


def get_unused_port():
    """Get an unused port."""
    new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    new_socket.bind(("localhost", 0))
    port = new_socket.getsockname()[1]
    new_socket.close()
    return port


@dataclass
class LocalFork:
    """Use a docker container to test contract calls."""

    fork_url: str
    fork_block_number: int

    host: str = "http://localhost"
    port: int = 8546
    container: Optional[Container] = None
    run_command: str = "--fork-url {fork_url} --fork-block-number {fork_block_number} --host 0.0.0.0 --port {port}"

    def stop(self):
        """Stop the docker container."""
        # we force the container to stop
        self.container.stop()
        self.container.remove(force=True)
        wait = 0
        while self.is_ready():
            if wait > 10:
                raise TimeoutError("Docker fork did not stop in time.")
            wait += 1
            time.sleep(1)

    def is_ready(self):
        """Check if the docker container is ready."""
        try:
            res = requests.post(
                f"{self.host}:{self.port}",
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 1,
                },
                timeout=1,
            )
        except requests.exceptions.ConnectionError:
            return False
        except requests.exceptions.ReadTimeout:
            return False
        if res.status_code != 200:
            return False
        return int(res.json()["result"], 16) == self.fork_block_number

    def run(self):
        """Run the docker container in a background process."""
        client = DockerClient.from_env()
        self.container = client.containers.run(
            image="ghcr.io/foundry-rs/foundry:latest",
            entrypoint="/usr/local/bin/anvil",
            command=self.run_command.format(
                fork_url=self.fork_url,
                fork_block_number=self.fork_block_number,
                port=self.port,
            ),
            ports={f"{self.port}/tcp": self.port},
            detach=True,
            volumes={
                "foundry": {"bind": "/root/.foundry/cache/rpc/", "mode": "rw"},
            },
        )
        wait = 0
        while not self.is_ready():
            time.sleep(1)
            wait += 1
            if wait > 15:
                raise TimeoutError("Docker fork did not start in time.")

    def restart_from_block(self, block_number: int):
        """Restart the docker container from a given block number."""
        self.stop()
        self.fork_block_number = block_number
        self.run()
