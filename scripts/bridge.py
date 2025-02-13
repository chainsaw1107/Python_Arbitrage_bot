"""
Script to bridge from 2 chains
"""

import time


from enum import Enum


class BridgeStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING_CONFIRMATIONS = "pending_confirmations"
    PENDING_CLAIM = "pending_claim"


class Bridger:
    def submit_to_bridge(self, from_chain, to_chain, amount):
        """
        Submit the transaction to the bridge
        """
        # we submit the tx to the bridge

    def check_bridge_status(self, tx_hash, receipt, value):
        """
        Check the status of the bridge transaction. We effectively check the
        """
        raise NotImplementedError

    def check_pending_balance(self):
        """
        Check the pending balance of the bridge
        """
        raise NotImplementedError

    def claim_from_bridge(self):
        """
        Claim the transaction from the bridge
        """
        raise NotImplementedError

    def bridge(self):
        """
        Bridge the tokens from one chain to another
        """
        result = self.submit_to_bridge()
        status = self.check_bridge_status(result)
        while status is BridgeStatus.PENDING_CONFIRMATIONS:
            time.sleep(5)
            status = self.check_bridge_status(result)
        if status is BridgeStatus.SUCCESS:
            result = self.claim_from_bridge()
            status = self.check_bridge_status(result)
            while status is BridgeStatus.PENDING_CLAIM:
                time.sleep(5)
                status = self.check_bridge_status(result)
            return status
        return status

    def wrap(self):
        """
        Wrap the tokens
        """
        raise NotImplementedError

    def unwrap(self):
        """
        Unwrap the tokens
        """
        raise NotImplementedError


class GnosisXdaiBridger(Bridger):
    def __init__(self, web3, logger):
        self.web3 = web3
        self.logger = logger

    def submit_to_bridge(self, from_chain, to_chain, amount):
        """
        Submit the transaction to the bridge
        """

    def wrap(self):
        """
        Wrap the tokens
        """
        raise NotImplementedError

    def unwrap(self):
        """
        Example tx here;
        https://gnosisscan.io/tx/0x34a4de6c0461d9747df72ee3e967cf78633d6ec7322cf820872d9da1e6cea6d3

        https://gnosisscan.io/address/0xe91d153e0b41518a2ce8dd3d7944fa863463a97d#writeContract

        """
        raise NotImplementedError
