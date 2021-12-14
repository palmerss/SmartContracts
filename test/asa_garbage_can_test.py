import base64
import time

import pytest
from algosdk.v2client import algod
from algosdk import account, mnemonic, constants
from algosdk.encoding import encode_address, is_valid_address
from algosdk.error import AlgodHTTPError, TemplateInputError
from akita_inu_asa_utils import read_local_state, read_global_state, wait_for_txn_confirmation

NUM_TEST_ASSET = int(1e6)

@pytest.fixture(scope='class')
def test_config():
    from .testing_utils import load_test_config
    return load_test_config()


@pytest.fixture(scope='class')
def client(test_config):
    algod_address = test_config['algodAddress']
    algod_token = test_config['algodToken']
    client = algod.AlgodClient(algod_token, algod_address)
    return client


@pytest.fixture(scope='class')
def wallet_1(test_config):
    from akita_inu_asa_utils import generate_new_account
    from .testing_utils import fund_account
    wallet_mnemonic, private_key, public_key = generate_new_account()

    wallet_1 = {'mnemonic': wallet_mnemonic, 'public_key': public_key, 'private_key': private_key}

    # fund the wallet
    fund_account(wallet_1['public_key'], test_config['fund_account_mnemonic'])
    return wallet_1


@pytest.fixture(scope='class')
def asset_id(test_config, wallet_1, client):
    from akita_inu_asa_utils import (create_asa_signed_txn,
                                     asset_id_from_create_txn)
    params = client.suggested_params()
    txn, txn_id = create_asa_signed_txn(wallet_1['public_key'],
                                        wallet_1['private_key'],
                                        params,
                                        total=NUM_TEST_ASSET)
    client.send_transactions([txn])
    wait_for_txn_confirmation(client, txn_id, 5)
    return asset_id_from_create_txn(client, txn_id)


# This fixture also serves as the deploy test
# Note this fixture also shares the exact same application with all the test....unfortunately order in which test are
# called in this file depend on order
@pytest.fixture(scope='class')
def app_id(test_config, wallet_1):
    from contracts.ASAGarbageCan.deployment import deploy

    algod_address = test_config['algodAddress']
    algod_token = test_config['algodToken']
    creator_mnemonic = wallet_1['mnemonic']
    app_id = deploy(algod_address, algod_token, creator_mnemonic)
    return app_id


def clear_build_folder():
    import os
    for file in os.scandir('./build'):
        os.remove(file.path)


class TestTimedAssetLockContract:
    def test_build(self, client):
        from contracts.ASAGarbageCan.program import compile_app
        clear_build_folder()
        import os
        compile_app(client)
        assert os.path.exists('./build/asa_garbage_can_approval.compiled')
        assert os.path.exists('./build/asa_garbage_can_clear.compiled')
        assert os.path.exists('./build/asa_garbage_can_approval.teal')
        assert os.path.exists('./build/asa_garbage_can_clear.teal')
        assert os.path.exists('./build/globalSchema')
        assert os.path.exists('./build/globalSchema')

    def test_deploy(self, app_id, client, wallet_1):
        from akita_inu_asa_utils import get_asset_balance, get_application_address
        from algosdk.future import transaction

        assert app_id
        app_address = get_application_address(app_id)
        txn0 = transaction.PaymentTxn(wallet_1['public_key'],
                                      client.suggested_params(),
                                      app_address,
                                      101000)
        txn0 = txn0.sign(wallet_1['private_key'])
        txn_id = client.send_transactions([txn0])
        wait_for_txn_confirmation(client, txn_id, 5)

    def test_opt_in_asset(self, app_id, client, asset_id, wallet_1):
        from akita_inu_asa_utils import get_asset_balance, get_application_address
        from algosdk.future import transaction


        app_address = get_application_address(app_id)
        txn0 = transaction.PaymentTxn(wallet_1['public_key'],
                                               client.suggested_params(),
                                               app_address,
                                               100000)

        app_args = [asset_id.to_bytes(8, "big")]
        txn1 = transaction.ApplicationNoOpTxn(wallet_1['public_key'],
                                               client.suggested_params(),
                                               app_id,
                                               app_args,
                                               foreign_assets=[asset_id])

        grouped = transaction.assign_group_id([txn0, txn1])
        grouped = [grouped[0].sign(wallet_1['private_key']),
                   grouped[1].sign(wallet_1['private_key'])]
        txn_id = client.send_transactions(grouped)
        wait_for_txn_confirmation(client, txn_id, 5)

        assert get_asset_balance(client, app_address, asset_id) == 0

        txn0 = transaction.AssetTransferTxn(wallet_1['public_key'],
                                            client.suggested_params(),
                                            app_address,
                                            10,
                                            asset_id)
        txn0 = txn0.sign(wallet_1['private_key'])
        txn_id = client.send_transactions([txn0])

        wait_for_txn_confirmation(client, txn_id, 5)

        assert get_asset_balance(client, app_address, asset_id) == 10

