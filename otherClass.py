import os
import traceback
from web3 import Web3
from dbClass import dbCalls

class otherCalls(object):
    def __init__(self, config):
        self.config = config
        self.db = dbCalls(config)
        self.w3 = self.getWeb3Instance()
        self.privatekey = os.getenv(self.config['eth']['seedenvname'], self.config['eth']['privateKey'])

        self.lastScannedBlock = self.db.lastScannedBlock("ETH")

    def getWeb3Instance(self):
        instance = None

        if self.config['eth']['node'].startswith('http'):
            instance = Web3(Web3.HTTPProvider(self.config['eth']['node']))
        else:
            instance = Web3()

        return instance

    def currentBlock(self):
        result = self.w3.eth.blockNumber

        return result

    def getBlock(self, height):
        return self.w3.eth.getBlock(height)

    def currentBalance(self):
        contract = self.w3.eth.getBalance(config['eth']['gatewayAddress'])
        balance /= pow(10, self.config['eth']['contract']['decimals'])

        return int(round(balance))

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

        if transaction['to'] == self.config['eth']['gatewayAddress']:
            transactionreceipt = self.w3.eth.getTransactionReceipt(tx)
            if transactionreceipt['status']:
                sender = transaction['from']
                recipient = transaction['to']
                amount = transaction['value'] / 10 ** self.config['eth']['decimals']

                if not self.db.didWeSendTx(tx.hex()): 
                    result = { 'sender': sender, 'function': 'transfer', 'recipient': recipient, 'amount': amount, 'id': tx.hex() }

        return result

    def sendTx(self, targetAddress, amount, gasprice = None, gas = None):
        amount -= self.config['eth']['fee']
        amount *= pow(10, self.config['eth']['decimals'])
        amount = int(round(amount))

        nonce = self.w3.eth.getTransactionCount(self.config['eth']['gatewayAddress'], 'pending')

        if gasprice == None:
            if self.config['eth']['gasprice'] > 0:
                gasprice = self.w3.toWei(self.config['eth']['gasprice'], 'gwei')
            else:
                gasprice = int(self.w3.eth.gasPrice * 1.1)

        if gas == None:
            gas = self.config['eth']['gas']

        tx = {
            'chainId': self.config['eth']['chainid'],
            'to': targetAddress,
            'value': amount,
            'gas': self.config['eth']['gas'],
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

