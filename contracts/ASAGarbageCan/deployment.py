from algosdk.future import transaction
from algosdk import account, mnemonic, logic, encoding
from akita_inu_asa_utils import *
from pyteal import *


def deploy_app(client, private_key, approval_program, clear_program, global_schema, local_schema):
    # define sender as creator
    public_key = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = transaction.OnComplete.NoOpOC.real

    # get node suggested parameters
    params = client.suggested_params()

    signed_txn, tx_id = create_app_signed_txn(private_key,
                                              public_key,
                                              params,
                                              on_complete,
                                              approval_program,
                                              clear_program,
                                              global_schema,
                                              local_schema)

    # send transaction
    client.send_transactions([signed_txn])

    wait_for_txn_confirmation(client, tx_id, 5)

    # display results
    transaction_response = client.pending_transaction_info(tx_id)
    app_id = transaction_response['application-index']
    print("Deployed new app-id: " + str(app_id))
    print("Deployed application address: " +
          encoding.encode_address(encoding.checksum(b'appID' + app_id.to_bytes(8, 'big'))))

    return app_id

def deploy(algod_address, algod_token, creator_mnemonic):

    private_key = mnemonic.to_private_key(creator_mnemonic)
    algod_client = get_algod_client(algod_token,
                                    algod_address)

    approval_program = load_compiled(file_path='asa_garbage_can_approval.compiled')
    clear_program = load_compiled(file_path='asa_garbage_can_clear.compiled')

    global_schema = load_schema(file_path='globalSchema')
    local_schema = load_schema(file_path='localSchema')

    app_id = deploy_app(algod_client,
                        private_key,
                        approval_program,
                        clear_program,
                        global_schema,
                        local_schema)
    return app_id
