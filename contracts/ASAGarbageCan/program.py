from akita_inu_asa_utils import *
from pyteal import *


def approval_program():
    # Keys for the global data stored by this smart contract.

    @Subroutine(TealType.none)
    def opt_in_asset(asset_id_key):
        return Seq(
                    InnerTxnBuilder.Begin(),
                    InnerTxnBuilder.SetFields(
                        {
                            # Send 0 units of the asset to itself to opt-in.
                            TxnField.type_enum: TxnType.AssetTransfer,
                            TxnField.xfer_asset: asset_id_key,
                            TxnField.asset_receiver: Global.current_application_address(),
                        }
                    ),
                    InnerTxnBuilder.Submit(),
                )

    on_create = Seq(
        Approve()
    )

    assert_garbage_format = Seq(
        Assert(And(Global.group_size() == Int(2),
                   Gtxn[0].type_enum() == TxnType.Payment,
                   Gtxn[1].application_args.length() == Int(1)))
    )

    add_new_garbage_can = Seq(
        assert_garbage_format,
        opt_in_asset(Btoi(Gtxn[1].application_args[0])),
        Approve()
    )

    # Application router for this smart contract.
    program = Cond(
        [
            Or(
                # Your fees shouldn't exceed an unreasonable amount
                Txn.fee() > Int(3000),
                # No rekeys allowed (just to be safe)
                Txn.rekey_to() != Global.zero_address(),
                # This smart contract cannot be closed out.
                Txn.on_completion() == OnComplete.CloseOut,
                # This smart contract cannot be updated.
                Txn.on_completion() == OnComplete.UpdateApplication,
                # This smart contract cannot be cleared of local state
                Txn.on_completion() == OnComplete.ClearState,
            ),
            Reject(),
        ],

        # single transactions
        [Txn.application_id() == Int(0), on_create],
        [Txn.on_completion() == OnComplete.OptIn, Approve()],
        [Txn.on_completion() == OnComplete.NoOp, add_new_garbage_can],
        [Txn.on_completion() == OnComplete.DeleteApplication, Reject()],
    )

    return compileTeal(program, Mode.Application, version=5)


def clear_program():
    return compileTeal(Reject(), Mode.Application, version=5)


def compile_app(algod_client):
    dump_teal_assembly('asa_garbage_can_approval.teal', approval_program)
    dump_teal_assembly('asa_garbage_can_clear.teal', clear_program)

    compile_program(algod_client, approval_program(), 'asa_garbage_can_approval.compiled')
    compile_program(algod_client, clear_program(), 'asa_garbage_can_clear.compiled')

    write_schema(file_path='localSchema',
                 num_ints=0,
                 num_bytes=0)
    write_schema(file_path='globalSchema',
                 num_ints=0,
                 num_bytes=0)
