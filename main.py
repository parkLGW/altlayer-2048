import json
import copy
import math

from typing import List, Optional
from random import randint

from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
from eth_account.messages import encode_structured_data

class AltLayer:
    def __init__(self):
        pass

    def _getLogArgs(self, logs: List[dict], event_name: str, contract: Contract, error: Optional[str] = None):
        event_abi = next((item for item in contract.abi if item["name"] == event_name), None)
        if not event_abi:
            raise ValueError(f"No ABI found for event {event_name}")

        for log in logs:
            decoded_log = contract.events.GameStarted().process_log(log)
            if decoded_log:
                return decoded_log["args"]

        if error is not None:
            raise ValueError(error)
        else:
            raise ValueError(f"No related {event_name} event")

    def _trim(self, row, direction=0):
        return ([0, 0, 0, 0] + [n for n in row if n])[-4:] if direction else ([n for n in row if n] + [0, 0, 0, 0])[:4]

    def _merge(self, row, direction):
        if row[1] and row[2] and row[1] == row[2]:
            return self._trim([row[0], row[1] * 2, 0, row[3]], direction=direction)
        if row[0] and row[1] and row[0] == row[1]:
            row[0] = row[0] * 2
            row[1] = 0
        if row[2] and row[3] and row[2] == row[3]:
            row[2] = row[2] * 2
            row[3] = 0

        return self._trim(row, direction=direction)

    # 模拟给定方向的移动
    def _simulate_move(self, board, direction):
        test_board = copy.deepcopy(board)

        if direction == 'left':
            for i, row in enumerate(test_board):
                test_board[i] = self._merge(self._trim(row, direction=0), direction=0)
        elif direction == 'right':
            for i, row in enumerate(test_board):
                test_board[i] = self._merge(self._trim(row, direction=1), direction=1)
        elif direction == 'down':
            for j in range(len(test_board[0])):
                col = [test_board[i][j] for i in range(len(test_board))]
                col = self._merge(self._trim(col, direction=1), direction=1)
                for i in range(len(test_board)):
                    test_board[i][j] = col[i]
        else:
            for j in range(len(test_board[0])):
                col = [test_board[i][j] for i in range(len(test_board))]
                col = self._merge(self._trim(col, direction=0), direction=0)
                for i in range(len(test_board)):
                    test_board[i][j] = col[i]

        return test_board

    def _count_empty(self, board):
        empty_cells = 0
        for row in board:
            empty_cells += row.count(0)
        return empty_cells

    def _count_merged(self, board1, board2):
        merged_cells = 0

        board1_arr = [element for sublist in board1 for element in sublist]
        board1_arr.sort(reverse=True)
        board2_arr = [element for sublist in board2 for element in sublist]
        board2_arr.sort(reverse=True)

        if board1_arr == board2_arr:
            return 0

        for i in range(len(board1_arr)):
            if board1_arr[i] != 0 and board2_arr[i] != 0 and board1_arr[i] != board2_arr[i]:
                merged_cells += 1

        return merged_cells

    def _get_max_value(self, board):
        return int(math.log(max(max(row) for row in board), 2))

    def _get_score(self, board, direction):
        board_after_move = self._simulate_move(board, direction)

        empty_cells = self._count_empty(board_after_move)
        merged_cells = self._count_merged(board, board_after_move)
        max_value = self._get_max_value(board_after_move)

        score = empty_cells + merged_cells * 2 + max_value

        return score

    def _move_strategy(self, board):
        max_score = -1
        best_direction = None

        for direction in ['left', 'right', 'up', 'down']:
            score = self._get_score(board, direction)
            if score > max_score:
                max_score = score
                best_direction = direction
            elif score == max_score and not randint(0, 2):
                best_direction = direction

        return best_direction

    def start_game(self, address, private_key, proxies=None):
        f = open('abi.json', 'r', encoding='utf-8')
        contract_2048 = json.load(f)['2048']
        abi = contract_2048['abi']
        contract_address = Web3.to_checksum_address(contract_2048['contract'])
        rpc = contract_2048['rpc']

        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs=proxies))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        contract = w3.eth.contract(address=contract_address, abi=abi)
        transaction = contract.functions.start().build_transaction({
            'gasPrice': 0,
            'nonce': w3.eth.get_transaction_count(account=address),
            'gas': 2100000
        })
        signed_transaction = w3.eth.account.sign_transaction(transaction, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_transaction.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(receipt['blockHash'].hex())
        logs = receipt['logs']
        game_id = self._getLogArgs(logs, 'GameStarted', contract).id
        print(f"game id:{game_id}")

        ended = contract.functions.gameEnded(game_id).call()

        while not ended:
            try:
                board_array = contract.functions.getBoard(game_id).call()
                board = [board_array[i:i + 4] for i in range(0, len(board_array), 4)]
                direction = self._move_strategy(board)
                print(f"当前结果：")
                for row in board:
                    print(row)
                print(f"移动方向：{direction}")
                if direction == "left":
                    transaction = contract.functions.left(game_id).build_transaction({
                        'gasPrice': 0,
                        'nonce': w3.eth.get_transaction_count(account=address),
                        'gas': 2100000
                    })
                elif direction == "right":
                    transaction = contract.functions.right(game_id).build_transaction({
                        'gasPrice': 0,
                        'nonce': w3.eth.get_transaction_count(account=address),
                        'gas': 2100000
                    })
                elif direction == "up":
                    transaction = contract.functions.up(game_id).build_transaction({
                        'gasPrice': 0,
                        'nonce': w3.eth.get_transaction_count(account=address),
                        'gas': 2100000
                    })
                else:
                    transaction = contract.functions.down(game_id).build_transaction({
                        'gasPrice': 0,
                        'nonce': w3.eth.get_transaction_count(account=address),
                        'gas': 2100000
                    })
                signed_transaction = w3.eth.account.sign_transaction(transaction, private_key=private_key)
                tx_hash = w3.eth.send_raw_transaction(signed_transaction.rawTransaction)
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                # print(receipt['logs'])
                ended = contract.functions.gameEnded(game_id).call()
            except Exception as e:
                print(f"链上错误，忽略：{e}")
                continue

        score = contract.functions.scores(game_id).call()
        return score

    def register_2048(self, address, private_key, proxies=None):
        """
        注册，绑定随机账号
        :param address:
        :param private_key:
        :param proxies:
        :return:
        """
        address = Web3.to_checksum_address(address)
        f = open('abi.json', 'r', encoding='utf-8')
        contract_portal = json.load(f)['portal']
        f.close()
        abi = contract_portal['abi']
        contract_address = Web3.to_checksum_address(contract_portal['contract'])
        rpc = contract_portal['rpc']

        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs=proxies))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        contract = w3.eth.contract(address=contract_address, abi=abi)
        _, name, version, chain_id, verifying_contract, _, _ = contract.functions.eip712Domain().call()
        nonce = contract.functions.nonces(address).call()

        # 生成随机账号，绑定主账号后交互2048合约
        target_account = w3.eth.account.create()

        domain = {
            "name": name,
            "version": version,
            "chainId": int(chain_id),
            "verifyingContract": verifying_contract
        }
        types = {
            'User': [
                {'name': 'signer', 'type': 'address'},
                {'name': 'nonce', 'type': 'uint256'},
                {'name': 'target', 'type': 'address'}
            ],
            'EIP712Domain': [
                {'name': 'name', 'type': 'string'},
                {'name': 'version', 'type': 'string'},
                {'name': 'chainId', 'type': 'uint256'},
                {'name': 'verifyingContract', 'type': 'address'}
            ]
        }
        value = {
            'signer': address,
            'nonce': int(nonce) + 1,
            'target': target_account.address
        }
        pack_data = {
            "domain": domain,
            "types": types,
            "message": value,
            "primaryType": "User"
        }

        encode_data = encode_structured_data(pack_data)
        signed_message = w3.eth.account.sign_message(encode_data, private_key=private_key)
        signature = Web3.to_bytes(signed_message['signature'])
        print(f"签名：{signature.hex()}")

        nonce = int(nonce)
        transaction = contract.functions.register(signature, address, nonce + 1).build_transaction({
            'gasPrice': 0,
            'nonce': w3.eth.get_transaction_count(account=target_account.address),
            'gas': 2100000
        })
        signed_transaction = w3.eth.account.sign_transaction(transaction, private_key=target_account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_transaction.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        logs = receipt['logs']
        # print(logs)

        fr = open('temp_address.json', 'r', encoding='utf-8')
        address_dict = json.load(fr)
        address_dict[address] = {
            "temp_address": target_account.address,
            "temp_key": Web3.to_hex(target_account.key)
        }
        fr.close()
        fw = open('temp_address.json', 'w', encoding='utf-8')
        json.dump(address_dict, fw, ensure_ascii=False, indent=2)
        fw.close()

        return target_account.address, Web3.to_hex(target_account.key)


def play_2048():
    f = open('accounts.txt', 'r')
    accounts = f.readlines()
    f.close()
    f = open('proxies.txt', 'r', encoding='utf-8')
    proxies = f.readlines()
    f.close()

    alt = AltLayer()
    for i, account in enumerate(accounts):
        address, private_key = account.strip().split(',')
        address = Web3.to_checksum_address(address)
        print(f"账号{i + 1}:{address}")

        proxies_conf = None
        if len(proxies) != 0:
            proxies_conf = {
                "proxies": {
                    "http": f"socks5://{proxies[i]}",
                    "https": f"socks5://{proxies[i]}"
                }
            }

        f = open('temp_address.json', 'r', encoding='utf-8')
        account_dict = json.load(f)
        f.close()

        final_score = 0
        while final_score < 2000:
            if account_dict.get(address):
                random_address, random_key = account_dict[address]['temp_address']['temp_key']
            else:
                random_address, random_key = alt.register_2048(address, private_key, proxies_conf)
            final_score = alt.start_game(random_address, random_key, proxies_conf)
        print(f"账号{i + 1}得分：{final_score}")


if __name__ == '__main__':
    play_2048()
