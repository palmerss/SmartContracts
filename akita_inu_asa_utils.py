import base64
from algosdk.v2client import algod
from algosdk.future import transaction
from algosdk import encoding
from joblib import dump, load
import json
import os

def getApplicationAddress(app_id):
    return encoding.encode_address(encoding.checksum(b'appID' + app_id.to_bytes(8, 'big')))

def deleteAllApps(client, public_key, private_key):
    apps = client.account_info("W5RWJVUUJEH67D6DMW7Z6PCYI2TQNZYILEXTP4YP5XI5VVPB6T5O7NPZHU")['created-apps']
    for app in apps:
        app_id = app['id']
        delete_app_signed_txn(private_key, public_key, client.suggested_params(), app_id)


def check_build_dir():
    if not os.path.exists('build'):
        os.mkdir('build')


def compile_program(client, source_code, file_path=None):
    compile_response = client.compile(source_code)
    if file_path == None:
        return base64.b64decode(compile_response['result'])
    else:
        check_build_dir()
        dump(base64.b64decode(compile_response['result']), 'build/' + file_path)


def dump_teal_assembly(file_path, program_fn_pointer):
    check_build_dir()
    with open('build/' + file_path, 'w') as f:
        compiled = program_fn_pointer()
        f.write(compiled)


def load_compiled(file_path):
    try:
        compiled = load('build/' + file_path)
    except:
        print("Error reading source file...exiting")
        exit(-1)
    return compiled


def load_developer_config(file_path='DeveloperConfig.json'):
    fp = open(file_path)
    return json.load(fp)


def get_algod_client(token, address):
    return algod.AlgodClient(token, address)


def write_schema(file_path, num_ints, num_bytes):
    schema = transaction.StateSchema(num_ints, num_bytes)
    dump(schema, 'build/' + file_path)


def load_schema(file_path):
    return load('build/' + file_path)


def wait_for_txn_confirmation(client, transaction_id, timeout):
    """
    Wait until the transaction is confirmed or rejected, or until 'timeout'
    number of rounds have passed.
    Args:
        transaction_id (str): the transaction to wait for
        timeout (int): maximum number of rounds to wait
    Returns:
        dict: pending transaction information, or throws an error if the transaction
            is not confirmed or rejected in the next timeout rounds
    """
    start_round = client.status()["last-round"] + 1
    current_round = start_round

    while current_round < start_round + timeout:
        try:
            pending_txn = client.pending_transaction_info(transaction_id)
        except Exception:
            return
        if pending_txn.get("confirmed-round", 0) > 0:
            return pending_txn
        elif pending_txn["pool-error"]:
            raise Exception(
                'pool error: {}'.format(pending_txn["pool-error"]))
        client.status_after_block(current_round)
        current_round += 1
    raise Exception(
        'pending tx not found in timeout rounds, timeout value = : {}'.format(timeout))

def sign_txn(unsigned_txn, private_key):
    """
        signs the provided unsigned transaction
            Args:
                unsigned_txn (???): transaction to be signed
                private_key (str): private key of sender
            Returns:
                ???: signed transaction
    """
    signed_tx = unsigned_txn.sign(private_key)
    return signed_tx

def create_app_signed_txn(private_key,
                          public_key,
                          params,
                          on_complete,
                          approval_program,
                          clear_program,
                          global_schema,
                          local_schema,
                          app_args):
    """
        Creates an signed "create app" transaction to an application
            Args:
                private_key (str): private key of sender
                public_key (str): public key of sender
                params (???): parameters obtained from algod
                on_complete (???):
                approval_program (???): compiled approval program
                clear_program (???): compiled clear program
                global_schema (???): global schema variables
                local_schema (???): local schema variables
            Returns:
                tuple: Tuple containing the signed transaction and signed transaction id
    """
    unsigned_txn = transaction.ApplicationCreateTxn(public_key,
                                                    params,
                                                    on_complete,
                                                    approval_program,
                                                    clear_program,
                                                    global_schema,
                                                    local_schema,
                                                    app_args)

    signed_txn = sign_txn(unsigned_txn, private_key)
    return signed_txn, signed_txn.transaction.get_txid()


def opt_in_app_signed_txn(private_key,
                          public_key,
                          params,
                          app_id,
                          foreign_assets=None,
                          app_args=None):
    """
    Creates and signs an "opt in" transaction to an application
        Args:
            private_key (str): private key of sender
            public_key (str): public key of sender
            params (???): parameters obtained from algod
            app_id (int): id of application
        Returns:
            tuple: Tuple containing the signed transaction and signed transaction id
    """
    txn = transaction.ApplicationOptInTxn(public_key,
                                          params,
                                          app_id,
                                          foreign_assets=foreign_assets,
                                          app_args=app_args)
    signed_txn = sign_txn(txn, private_key)
    return signed_txn, signed_txn.transaction.get_txid()


def noop_app_signed_txn(private_key,
                          public_key,
                          params,
                          app_id,
                          asset_ids=None):
    """
    Creates and signs an "noOp" transaction to an application
        Args:
            private_key (str): private key of sender
            public_key (str): public key of sender
            params (???): parameters obtained from algod
            app_id (int): id of application
            asset_id (int): id of asset if any
        Returns:
            tuple: Tuple containing the signed transaction and signed transaction id
    """
    txn = transaction.ApplicationNoOpTxn(public_key,
                                         params,
                                         app_id,
                                         foreign_assets=asset_ids)
    signed_txn = sign_txn(txn, private_key)
    return signed_txn, signed_txn.transaction.get_txid()

def delete_app_signed_txn(private_key,
                          public_key,
                          params,
                          app_id,
                          asset_ids=None):
    """
    Creates and signs an "noOp" transaction to an application
        Args:
            private_key (str): private key of sender
            public_key (str): public key of sender
            params (???): parameters obtained from algod
            app_id (int): id of application
            asset_id (int): id of asset if any
        Returns:
            tuple: Tuple containing the signed transaction and signed transaction id
    """
    txn = transaction.ApplicationDeleteTxn(public_key,
                                         params,
                                         app_id,
                                         foreign_assets=asset_ids)
    signed_txn = sign_txn(txn, private_key)
    return signed_txn, signed_txn.transaction.get_txid()

def create_asa_signed_txn(public_key, private_key, params, total=1e6, default_frozen=False, decimals=0):
    txn = transaction.AssetConfigTxn(
        sender=public_key,
        sp=params,
        total=total,
        default_frozen=default_frozen,
        manager=public_key,
        reserve=public_key,
        freeze=public_key,
        clawback=public_key,
        url="https://path/to/my/asset/details",
        decimals=decimals)

    signed_txn = sign_txn(txn, private_key)
    return signed_txn

def transfer_signed_txn(sender_private_key,
                        sender_public_key,
                        receiver_public_key,
                        amount,
                        params):
    txn = transaction.PaymentTxn(sender_public_key,
                                 params,
                                 receiver_public_key,
                                 amount)
    signed_txn = sign_txn(txn, sender_private_key)
    return signed_txn, signed_txn.transaction.get_txid()
