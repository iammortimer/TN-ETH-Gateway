import os
import traceback
from web3 import Web3
from dbClass import dbCalls
from dbPGClass import dbPGCalls

class otherCalls(object):
    def __init__(self, config):
        self.config = config

        if self.config['main']['use-pg']:
            self.db = dbPGCalls(config)
        else:
            self.db = dbCalls(config)

        self.w3 = self.getWeb3Instance()
        self.privatekey = os.getenv(self.config['other']['seedenvname'], self.config['other']['privateKey'])

        self.lastScannedBlock = self.db.lastScannedBlock("ETH")

    def getWeb3Instance(self):
        instance = None

        if self.config['other']['node'].startswith('http'):
            instance = Web3(Web3.HTTPProvider(self.config['other']['node']))
        else:
            instance = Web3()

        return instance

    def currentBlock(self):
        result = self.w3.eth.blockNumber

        return result

    def getBlock(self, height):
        return self.w3.eth.getBlock(height)

    def currentBalance(self):
        balance = self.w3.eth.getBalance(self.config['other']['gatewayAddress'])
        balance /= pow(10, self.config['other']['decimals'])

        return balance

    def normalizeAddress(self, address):
        if self.w3.isAddress(address):
            if self.w3.isChecksumAddress(address):
                return address
            else:
                return self.w3.toChecksumAddress(address)
        else:
            return "invalid address"

    def validateAddress(self, address):
        return self.w3.isAddress(address)

    def verifyTx(self, txId, sourceAddress = '', targetAddress = ''):
        if type(txId) == str:
            txid = txId
        else: 
            txid = txId.hex()

        tx = self.db.getExecuted(ethTxId=txid)

        try:
            verified = self.w3.eth.waitForTransactionReceipt(txid, timeout=120)

            if verified['status'] == 1:
                self.db.insVerified("ETH", txid, verified['blockNumber'])
                print('INFO: tx to eth verified!')

                self.db.delTunnel(sourceAddress, targetAddress)
            elif verified['status'] == 0:
                print('ERROR: tx failed to send!')
                self.resendTx(txId)
        except:
            self.db.insVerified("ETH", txid, 0)
            print('WARN: tx to eth not verified!')

    def checkTx(self, tx):
        #check the transaction
        result = None
        transaction = self.w3.eth.getTransaction(tx)

        if transaction['to'] == self.config['other']['gatewayAddress']:
            transactionreceipt = self.w3.eth.getTransactionReceipt(tx)
            if transactionreceipt['status']:
                sender = transaction['from']
                recipient = transaction['to']
                amount = transaction['value'] / 10 ** self.config['other']['decimals']

                if not self.db.didWeSendTx(tx.hex()): 
                    result = { 'sender': sender, 'function': 'transfer', 'recipient': recipient, 'amount': amount, 'id': tx.hex() }

        return result

    def sendTx(self, targetAddress, amount, gasprice = None, gas = None):
        amount -= self.config['other']['fee']
        amount *= pow(10, self.config['other']['decimals'])
        amount = int(round(amount))

        nonce = self.w3.eth.getTransactionCount(self.config['other']['gatewayAddress'], 'pending')

        if gasprice == None:
            if self.config['other']['gasprice'] > 0:
                gasprice = self.w3.toWei(self.config['other']['gasprice'], 'gwei')
            else:
                gasprice = int(self.w3.eth.gasPrice * 1.1)

        if gas == None:
            gas = self.config['other']['gas']

        tx = {
            'chainId': self.config['other']['chainid'],
            'to': targetAddress,
            'value': amount,
            'gas': self.config['other']['gas'],
            'gasPrice': gasprice,
            'nonce': nonce
        }
        signed_tx = self.w3.eth.account.signTransaction(tx, private_key=self.privatekey)
        txId = self.w3.eth.sendRawTransaction(signed_tx.rawTransaction)

        return txId

    def resendTx(self, txId):
        if type(txId) == str:
            txid = txId
        else: 
            txid = txId.hex()

        failedtx = self.db.getExecuted(ethTxId=txid)

        if len(failedtx) > 0:
            id = failedtx[0][0]
            sourceAddress = failedtx[0][1]
            targetAddress = failedtx[0][2]
            tnTxId = failedtx[0][3]
            amount = failedtx[0][6]

            self.db.insError(sourceAddress, targetAddress, tnTxId, txid, amount, 'tx failed on network - manual intervention required')
            print("ERROR: tx failed on network - manual intervention required: " + txid)
            self.db.updTunnel("error", sourceAddress, targetAddress, statusOld="verifying")

