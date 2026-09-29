import * as __compactRuntime from '@midnight-ntwrk/compact-runtime';
__compactRuntime.checkRuntimeVersion('0.19.0');

const _descriptor_0 = new __compactRuntime.CompactTypeUnsignedInteger(18446744073709551615n, 8);

const _descriptor_1 = new __compactRuntime.CompactTypeUnsignedInteger(340282366920938463463374607431768211455n, 16);

const _descriptor_2 = new __compactRuntime.CompactTypeBytes(32);

const _descriptor_3 = new __compactRuntime.CompactTypeUnsignedInteger(255n, 1);

class _Escrow_0 {
  alignment() {
    return _descriptor_1.alignment().concat(_descriptor_2.alignment().concat(_descriptor_2.alignment().concat(_descriptor_3.alignment().concat(_descriptor_2.alignment().concat(_descriptor_0.alignment().concat(_descriptor_0.alignment().concat(_descriptor_2.alignment().concat(_descriptor_2.alignment()))))))));
  }
  fromValue(value_0) {
    return {
      amount: _descriptor_1.fromValue(value_0),
      agentCommitment: _descriptor_2.fromValue(value_0),
      organizerCommitment: _descriptor_2.fromValue(value_0),
      state: _descriptor_3.fromValue(value_0),
      bookingRef: _descriptor_2.fromValue(value_0),
      deadline: _descriptor_0.fromValue(value_0),
      claimDeadline: _descriptor_0.fromValue(value_0),
      coinNonce: _descriptor_2.fromValue(value_0),
      coinColor: _descriptor_2.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_1.toValue(value_0.amount).concat(_descriptor_2.toValue(value_0.agentCommitment).concat(_descriptor_2.toValue(value_0.organizerCommitment).concat(_descriptor_3.toValue(value_0.state).concat(_descriptor_2.toValue(value_0.bookingRef).concat(_descriptor_0.toValue(value_0.deadline).concat(_descriptor_0.toValue(value_0.claimDeadline).concat(_descriptor_2.toValue(value_0.coinNonce).concat(_descriptor_2.toValue(value_0.coinColor)))))))));
  }
}

const _descriptor_4 = new _Escrow_0();

const _descriptor_5 = __compactRuntime.CompactTypeBoolean;

class _ZswapCoinPublicKey_0 {
  alignment() {
    return _descriptor_2.alignment();
  }
  fromValue(value_0) {
    return {
      bytes: _descriptor_2.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_2.toValue(value_0.bytes);
  }
}

const _descriptor_6 = new _ZswapCoinPublicKey_0();

class _QualifiedShieldedCoinInfo_0 {
  alignment() {
    return _descriptor_2.alignment().concat(_descriptor_2.alignment().concat(_descriptor_1.alignment().concat(_descriptor_0.alignment())));
  }
  fromValue(value_0) {
    return {
      nonce: _descriptor_2.fromValue(value_0),
      color: _descriptor_2.fromValue(value_0),
      value: _descriptor_1.fromValue(value_0),
      mt_index: _descriptor_0.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_2.toValue(value_0.nonce).concat(_descriptor_2.toValue(value_0.color).concat(_descriptor_1.toValue(value_0.value).concat(_descriptor_0.toValue(value_0.mt_index))));
  }
}

const _descriptor_7 = new _QualifiedShieldedCoinInfo_0();

const _descriptor_8 = new __compactRuntime.CompactTypeUnsignedInteger(65535n, 2);

class _ShieldedCoinInfo_0 {
  alignment() {
    return _descriptor_2.alignment().concat(_descriptor_2.alignment().concat(_descriptor_1.alignment()));
  }
  fromValue(value_0) {
    return {
      nonce: _descriptor_2.fromValue(value_0),
      color: _descriptor_2.fromValue(value_0),
      value: _descriptor_1.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_2.toValue(value_0.nonce).concat(_descriptor_2.toValue(value_0.color).concat(_descriptor_1.toValue(value_0.value)));
  }
}

const _descriptor_9 = new _ShieldedCoinInfo_0();

class _ContractAddress_0 {
  alignment() {
    return _descriptor_2.alignment();
  }
  fromValue(value_0) {
    return {
      bytes: _descriptor_2.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_2.toValue(value_0.bytes);
  }
}

const _descriptor_10 = new _ContractAddress_0();

class _Either_0 {
  alignment() {
    return _descriptor_5.alignment().concat(_descriptor_6.alignment().concat(_descriptor_10.alignment()));
  }
  fromValue(value_0) {
    return {
      is_left: _descriptor_5.fromValue(value_0),
      left: _descriptor_6.fromValue(value_0),
      right: _descriptor_10.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_5.toValue(value_0.is_left).concat(_descriptor_6.toValue(value_0.left).concat(_descriptor_10.toValue(value_0.right)));
  }
}

const _descriptor_11 = new _Either_0();

const _descriptor_12 = __compactRuntime.CompactTypeField;

const _descriptor_13 = new __compactRuntime.CompactTypeVector(2, _descriptor_2);

const _descriptor_14 = new __compactRuntime.CompactTypeBytes(21);

class _CoinPreimage_0 {
  alignment() {
    return _descriptor_14.alignment().concat(_descriptor_9.alignment().concat(_descriptor_5.alignment().concat(_descriptor_2.alignment())));
  }
  fromValue(value_0) {
    return {
      domain_sep: _descriptor_14.fromValue(value_0),
      info: _descriptor_9.fromValue(value_0),
      dataType: _descriptor_5.fromValue(value_0),
      data: _descriptor_2.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_14.toValue(value_0.domain_sep).concat(_descriptor_9.toValue(value_0.info).concat(_descriptor_5.toValue(value_0.dataType).concat(_descriptor_2.toValue(value_0.data))));
  }
}

const _descriptor_15 = new _CoinPreimage_0();

const _descriptor_16 = new __compactRuntime.CompactTypeVector(2, _descriptor_12);

class _Maybe_0 {
  alignment() {
    return _descriptor_5.alignment().concat(_descriptor_9.alignment());
  }
  fromValue(value_0) {
    return {
      is_some: _descriptor_5.fromValue(value_0),
      value: _descriptor_9.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_5.toValue(value_0.is_some).concat(_descriptor_9.toValue(value_0.value));
  }
}

const _descriptor_17 = new _Maybe_0();

class _ShieldedSendResult_0 {
  alignment() {
    return _descriptor_17.alignment().concat(_descriptor_9.alignment());
  }
  fromValue(value_0) {
    return {
      change: _descriptor_17.fromValue(value_0),
      sent: _descriptor_9.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_17.toValue(value_0.change).concat(_descriptor_9.toValue(value_0.sent));
  }
}

const _descriptor_18 = new _ShieldedSendResult_0();

class _Either_1 {
  alignment() {
    return _descriptor_5.alignment().concat(_descriptor_2.alignment().concat(_descriptor_2.alignment()));
  }
  fromValue(value_0) {
    return {
      is_left: _descriptor_5.fromValue(value_0),
      left: _descriptor_2.fromValue(value_0),
      right: _descriptor_2.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_5.toValue(value_0.is_left).concat(_descriptor_2.toValue(value_0.left).concat(_descriptor_2.toValue(value_0.right)));
  }
}

const _descriptor_19 = new _Either_1();

const _descriptor_20 = new __compactRuntime.CompactTypeUnsignedInteger(4294967295n, 4);

export class Contract {
  witnesses;
  constructor(...args_0) {
    if (args_0.length !== 1) {
      throw new __compactRuntime.CompactError(`Contract constructor: expected 1 argument, received ${args_0.length}`);
    }
    const witnesses_0 = args_0[0];
    if (typeof(witnesses_0) !== 'object') {
      throw new __compactRuntime.CompactError('first (witnesses) argument to Contract constructor is not an object');
    }
    if (typeof(witnesses_0.agentSecretKey) !== 'function') {
      throw new __compactRuntime.CompactError('first (witnesses) argument to Contract constructor does not contain a function-valued field named agentSecretKey');
    }
    if (typeof(witnesses_0.organizerSecretKey) !== 'function') {
      throw new __compactRuntime.CompactError('first (witnesses) argument to Contract constructor does not contain a function-valued field named organizerSecretKey');
    }
    this.witnesses = witnesses_0;
    this.circuits = {
      async agentCommitment(context, ...args_1) {
        return { result: pureCircuits.agentCommitment(...args_1), context };
      },
      async organizerCommitment(context, ...args_1) {
        return { result: pureCircuits.organizerCommitment(...args_1), context };
      },
      createEscrow: async (...args_1) => {
        if (args_1.length !== 9) {
          throw new __compactRuntime.CompactError(`createEscrow: expected 9 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const amount_0 = args_1[1];
        const organizerCommitmentInput_0 = args_1[2];
        const bookingRef_0 = args_1[3];
        const deadline_0 = args_1[4];
        const claimDeadline_0 = args_1[5];
        const deposit_0 = args_1[6];
        const agentPk_0 = args_1[7];
        const organizerPk_0 = args_1[8];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 1 (as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(amount_0) === 'bigint' && amount_0 >= 0n && amount_0 <= 340282366920938463463374607431768211455n)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'Uint<0..340282366920938463463374607431768211456>',
                                     amount_0)
        }
        if (!(organizerCommitmentInput_0.buffer instanceof ArrayBuffer && organizerCommitmentInput_0.BYTES_PER_ELEMENT === 1 && organizerCommitmentInput_0.length === 32)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'Bytes<32>',
                                     organizerCommitmentInput_0)
        }
        if (!(bookingRef_0.buffer instanceof ArrayBuffer && bookingRef_0.BYTES_PER_ELEMENT === 1 && bookingRef_0.length === 32)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'Bytes<32>',
                                     bookingRef_0)
        }
        if (!(typeof(deadline_0) === 'bigint' && deadline_0 >= 0n && deadline_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 4 (argument 5 as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'Uint<0..18446744073709551616>',
                                     deadline_0)
        }
        if (!(typeof(claimDeadline_0) === 'bigint' && claimDeadline_0 >= 0n && claimDeadline_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 5 (argument 6 as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'Uint<0..18446744073709551616>',
                                     claimDeadline_0)
        }
        if (!(typeof(deposit_0) === 'object' && deposit_0.nonce.buffer instanceof ArrayBuffer && deposit_0.nonce.BYTES_PER_ELEMENT === 1 && deposit_0.nonce.length === 32 && deposit_0.color.buffer instanceof ArrayBuffer && deposit_0.color.BYTES_PER_ELEMENT === 1 && deposit_0.color.length === 32 && typeof(deposit_0.value) === 'bigint' && deposit_0.value >= 0n && deposit_0.value <= 340282366920938463463374607431768211455n)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 6 (argument 7 as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'struct ShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>>',
                                     deposit_0)
        }
        if (!(typeof(agentPk_0) === 'object' && agentPk_0.bytes.buffer instanceof ArrayBuffer && agentPk_0.bytes.BYTES_PER_ELEMENT === 1 && agentPk_0.bytes.length === 32)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 7 (argument 8 as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'struct ZswapCoinPublicKey<bytes: Bytes<32>>',
                                     agentPk_0)
        }
        if (!(typeof(organizerPk_0) === 'object' && organizerPk_0.bytes.buffer instanceof ArrayBuffer && organizerPk_0.bytes.BYTES_PER_ELEMENT === 1 && organizerPk_0.bytes.length === 32)) {
          __compactRuntime.typeError('createEscrow',
                                     'argument 8 (argument 9 as invoked from Typescript)',
                                     'escrow.compact line 77 char 1',
                                     'struct ZswapCoinPublicKey<bytes: Bytes<32>>',
                                     organizerPk_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_1.toValue(amount_0).concat(_descriptor_2.toValue(organizerCommitmentInput_0).concat(_descriptor_2.toValue(bookingRef_0).concat(_descriptor_0.toValue(deadline_0).concat(_descriptor_0.toValue(claimDeadline_0).concat(_descriptor_9.toValue(deposit_0).concat(_descriptor_6.toValue(agentPk_0).concat(_descriptor_6.toValue(organizerPk_0)))))))),
            alignment: _descriptor_1.alignment().concat(_descriptor_2.alignment().concat(_descriptor_2.alignment().concat(_descriptor_0.alignment().concat(_descriptor_0.alignment().concat(_descriptor_9.alignment().concat(_descriptor_6.alignment().concat(_descriptor_6.alignment())))))))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._createEscrow_0(context,
                                                    partialProofData,
                                                    amount_0,
                                                    organizerCommitmentInput_0,
                                                    bookingRef_0,
                                                    deadline_0,
                                                    claimDeadline_0,
                                                    deposit_0,
                                                    agentPk_0,
                                                    organizerPk_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      releaseEscrow: async (...args_1) => {
        if (args_1.length !== 3) {
          throw new __compactRuntime.CompactError(`releaseEscrow: expected 3 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const escrowId_0 = args_1[1];
        const spendCoin_0 = args_1[2];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('releaseEscrow',
                                     'argument 1 (as invoked from Typescript)',
                                     'escrow.compact line 116 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(escrowId_0) === 'bigint' && escrowId_0 >= 0n && escrowId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('releaseEscrow',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'escrow.compact line 116 char 1',
                                     'Uint<0..18446744073709551616>',
                                     escrowId_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('releaseEscrow',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'escrow.compact line 116 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(escrowId_0).concat(_descriptor_7.toValue(spendCoin_0)),
            alignment: _descriptor_0.alignment().concat(_descriptor_7.alignment())
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._releaseEscrow_0(context,
                                                     partialProofData,
                                                     escrowId_0,
                                                     spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      refundEscrow: async (...args_1) => {
        if (args_1.length !== 3) {
          throw new __compactRuntime.CompactError(`refundEscrow: expected 3 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const escrowId_0 = args_1[1];
        const spendCoin_0 = args_1[2];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('refundEscrow',
                                     'argument 1 (as invoked from Typescript)',
                                     'escrow.compact line 151 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(escrowId_0) === 'bigint' && escrowId_0 >= 0n && escrowId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('refundEscrow',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'escrow.compact line 151 char 1',
                                     'Uint<0..18446744073709551616>',
                                     escrowId_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('refundEscrow',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'escrow.compact line 151 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(escrowId_0).concat(_descriptor_7.toValue(spendCoin_0)),
            alignment: _descriptor_0.alignment().concat(_descriptor_7.alignment())
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._refundEscrow_0(context,
                                                    partialProofData,
                                                    escrowId_0,
                                                    spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      timeoutRefund: async (...args_1) => {
        if (args_1.length !== 3) {
          throw new __compactRuntime.CompactError(`timeoutRefund: expected 3 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const escrowId_0 = args_1[1];
        const spendCoin_0 = args_1[2];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('timeoutRefund',
                                     'argument 1 (as invoked from Typescript)',
                                     'escrow.compact line 187 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(escrowId_0) === 'bigint' && escrowId_0 >= 0n && escrowId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('timeoutRefund',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'escrow.compact line 187 char 1',
                                     'Uint<0..18446744073709551616>',
                                     escrowId_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('timeoutRefund',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'escrow.compact line 187 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(escrowId_0).concat(_descriptor_7.toValue(spendCoin_0)),
            alignment: _descriptor_0.alignment().concat(_descriptor_7.alignment())
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._timeoutRefund_0(context,
                                                     partialProofData,
                                                     escrowId_0,
                                                     spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      mutualRefund: async (...args_1) => {
        if (args_1.length !== 3) {
          throw new __compactRuntime.CompactError(`mutualRefund: expected 3 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const escrowId_0 = args_1[1];
        const returnCoin_0 = args_1[2];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('mutualRefund',
                                     'argument 1 (as invoked from Typescript)',
                                     'escrow.compact line 232 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(escrowId_0) === 'bigint' && escrowId_0 >= 0n && escrowId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('mutualRefund',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'escrow.compact line 232 char 1',
                                     'Uint<0..18446744073709551616>',
                                     escrowId_0)
        }
        if (!(typeof(returnCoin_0) === 'object' && returnCoin_0.nonce.buffer instanceof ArrayBuffer && returnCoin_0.nonce.BYTES_PER_ELEMENT === 1 && returnCoin_0.nonce.length === 32 && returnCoin_0.color.buffer instanceof ArrayBuffer && returnCoin_0.color.BYTES_PER_ELEMENT === 1 && returnCoin_0.color.length === 32 && typeof(returnCoin_0.value) === 'bigint' && returnCoin_0.value >= 0n && returnCoin_0.value <= 340282366920938463463374607431768211455n && typeof(returnCoin_0.mt_index) === 'bigint' && returnCoin_0.mt_index >= 0n && returnCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('mutualRefund',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'escrow.compact line 232 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     returnCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(escrowId_0).concat(_descriptor_7.toValue(returnCoin_0)),
            alignment: _descriptor_0.alignment().concat(_descriptor_7.alignment())
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._mutualRefund_0(context,
                                                    partialProofData,
                                                    escrowId_0,
                                                    returnCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      autoRelease: async (...args_1) => {
        if (args_1.length !== 3) {
          throw new __compactRuntime.CompactError(`autoRelease: expected 3 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const escrowId_0 = args_1[1];
        const spendCoin_0 = args_1[2];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('autoRelease',
                                     'argument 1 (as invoked from Typescript)',
                                     'escrow.compact line 277 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(escrowId_0) === 'bigint' && escrowId_0 >= 0n && escrowId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('autoRelease',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'escrow.compact line 277 char 1',
                                     'Uint<0..18446744073709551616>',
                                     escrowId_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('autoRelease',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'escrow.compact line 277 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(escrowId_0).concat(_descriptor_7.toValue(spendCoin_0)),
            alignment: _descriptor_0.alignment().concat(_descriptor_7.alignment())
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._autoRelease_0(context,
                                                   partialProofData,
                                                   escrowId_0,
                                                   spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      isHeld: async (...args_1) => {
        if (args_1.length !== 2) {
          throw new __compactRuntime.CompactError(`isHeld: expected 2 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const escrowId_0 = args_1[1];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('isHeld',
                                     'argument 1 (as invoked from Typescript)',
                                     'escrow.compact line 310 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(escrowId_0) === 'bigint' && escrowId_0 >= 0n && escrowId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('isHeld',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'escrow.compact line 310 char 1',
                                     'Uint<0..18446744073709551616>',
                                     escrowId_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(escrowId_0),
            alignment: _descriptor_0.alignment()
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._isHeld_0(context,
                                              partialProofData,
                                              escrowId_0);
        partialProofData.output = { value: _descriptor_5.toValue(result_0), alignment: _descriptor_5.alignment() };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      }
    };
    this.impureCircuits = {
      createEscrow: this.circuits.createEscrow,
      releaseEscrow: this.circuits.releaseEscrow,
      refundEscrow: this.circuits.refundEscrow,
      timeoutRefund: this.circuits.timeoutRefund,
      mutualRefund: this.circuits.mutualRefund,
      autoRelease: this.circuits.autoRelease,
      isHeld: this.circuits.isHeld
    };
    this.provableCircuits = {
      createEscrow: this.circuits.createEscrow,
      releaseEscrow: this.circuits.releaseEscrow,
      refundEscrow: this.circuits.refundEscrow,
      timeoutRefund: this.circuits.timeoutRefund,
      mutualRefund: this.circuits.mutualRefund,
      autoRelease: this.circuits.autoRelease,
      isHeld: this.circuits.isHeld
    };
  }
  async initialState(...args_0) {
    if (args_0.length !== 1) {
      throw new __compactRuntime.CompactError(`Contract state constructor: expected 1 argument (as invoked from Typescript), received ${args_0.length}`);
    }
    const constructorContext_0 = args_0[0];
    if (typeof(constructorContext_0) !== 'object') {
      throw new __compactRuntime.CompactError(`Contract state constructor: expected 'constructorContext' in argument 1 (as invoked from Typescript) to be an object`);
    }
    if (!('initialPrivateState' in constructorContext_0)) {
      throw new __compactRuntime.CompactError(`Contract state constructor: expected 'initialPrivateState' in argument 1 (as invoked from Typescript)`);
    }
    if (!('initialZswapLocalState' in constructorContext_0)) {
      throw new __compactRuntime.CompactError(`Contract state constructor: expected 'initialZswapLocalState' in argument 1 (as invoked from Typescript)`);
    }
    if (typeof(constructorContext_0.initialZswapLocalState) !== 'object') {
      throw new __compactRuntime.CompactError(`Contract state constructor: expected 'initialZswapLocalState' in argument 1 (as invoked from Typescript) to be an object`);
    }
    const state_0 = new __compactRuntime.ContractState();
    let stateValue_0 = __compactRuntime.StateValue.newArray();
    stateValue_0 = stateValue_0.arrayPush(__compactRuntime.StateValue.newNull());
    stateValue_0 = stateValue_0.arrayPush(__compactRuntime.StateValue.newNull());
    stateValue_0 = stateValue_0.arrayPush(__compactRuntime.StateValue.newNull());
    stateValue_0 = stateValue_0.arrayPush(__compactRuntime.StateValue.newNull());
    state_0.data = new __compactRuntime.ChargedState(stateValue_0);
    state_0.setOperation('createEscrow', new __compactRuntime.ContractOperation());
    state_0.setOperation('releaseEscrow', new __compactRuntime.ContractOperation());
    state_0.setOperation('refundEscrow', new __compactRuntime.ContractOperation());
    state_0.setOperation('timeoutRefund', new __compactRuntime.ContractOperation());
    state_0.setOperation('mutualRefund', new __compactRuntime.ContractOperation());
    state_0.setOperation('autoRelease', new __compactRuntime.ContractOperation());
    state_0.setOperation('isHeld', new __compactRuntime.ContractOperation());
    const context = __compactRuntime.createCircuitContext('constructor', __compactRuntime.dummyContractAddress(), constructorContext_0.initialZswapLocalState.coinPublicKey, state_0.data, constructorContext_0.initialPrivateState);
    const partialProofData = {
      input: { value: [], alignment: [] },
      output: undefined,
      publicTranscript: [],
      privateTranscriptOutputs: []
    };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(0n),
                                                                                              alignment: _descriptor_3.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newMap(
                                                          new __compactRuntime.StateMap()
                                                        ).encode() } },
                                       { ins: { cached: false, n: 1 } }]);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(1n),
                                                                                              alignment: _descriptor_3.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(0n),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } }]);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(2n),
                                                                                              alignment: _descriptor_3.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newMap(
                                                          new __compactRuntime.StateMap()
                                                        ).encode() } },
                                       { ins: { cached: false, n: 1 } }]);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(3n),
                                                                                              alignment: _descriptor_3.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newMap(
                                                          new __compactRuntime.StateMap()
                                                        ).encode() } },
                                       { ins: { cached: false, n: 1 } }]);
    state_0.data = new __compactRuntime.ChargedState(context.callContext.currentQueryContext.state.state);
    return {
      currentContractState: state_0,
      currentPrivateState: context.callContext.currentPrivateState,
      currentZswapLocalState: context.callContext.currentZswapLocalState
    }
  }
  _some_0(value_0) { return { is_some: true, value: value_0 }; }
  _none_0() {
    return { is_some: false,
             value:
               { nonce: new Uint8Array(32), color: new Uint8Array(32), value: 0n } };
  }
  _left_0(value_0) {
    return { is_left: true, left: value_0, right: { bytes: new Uint8Array(32) } };
  }
  _right_0(value_0) {
    return { is_left: false, left: { bytes: new Uint8Array(32) }, right: value_0 };
  }
  async _receiveShielded_0(context, partialProofData, coin_0) {
    const recipient_0 = this._right_0(_descriptor_10.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                                 partialProofData,
                                                                                                 [
                                                                                                  { dup: { n: 2 } },
                                                                                                  { idx: { cached: true,
                                                                                                           pushPath: false,
                                                                                                           path: [
                                                                                                                  { tag: 'value',
                                                                                                                    value: { value: _descriptor_3.toValue(0n),
                                                                                                                             alignment: _descriptor_3.alignment() } }] } },
                                                                                                  { popeq: { cached: true,
                                                                                                             result: undefined } }]).value));
    this._createZswapOutput_0(context, partialProofData, coin_0, recipient_0);
    const tmp_0 = this._coinCommitment_0(coin_0, recipient_0);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { swap: { n: 0 } },
                                       { idx: { cached: true,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(1n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(tmp_0),
                                                                                              alignment: _descriptor_2.alignment() }).encode() } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newNull().encode() } },
                                       { ins: { cached: true, n: 2 } },
                                       { swap: { n: 0 } }]);
    return [];
  }
  async _sendShielded_0(context, partialProofData, input_0, recipient_0, value_0)
  {
    const selfAddr_0 = _descriptor_10.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                  partialProofData,
                                                                                  [
                                                                                   { dup: { n: 2 } },
                                                                                   { idx: { cached: true,
                                                                                            pushPath: false,
                                                                                            path: [
                                                                                                   { tag: 'value',
                                                                                                     value: { value: _descriptor_3.toValue(0n),
                                                                                                              alignment: _descriptor_3.alignment() } }] } },
                                                                                   { popeq: { cached: true,
                                                                                              result: undefined } }]).value);
    this._createZswapInput_0(context, partialProofData, input_0);
    const tmp_0 = this._coinNullifier_0(this._downcastQualifiedCoin_0(input_0),
                                        selfAddr_0);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { swap: { n: 0 } },
                                       { idx: { cached: true,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(0n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(tmp_0),
                                                                                              alignment: _descriptor_2.alignment() }).encode() } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newNull().encode() } },
                                       { ins: { cached: true, n: 2 } },
                                       { swap: { n: 0 } }]);
    let t_0;
    const change_0 = (t_0 = input_0.value,
                      (__compactRuntime.assert(t_0 >= value_0,
                                               'result of subtraction would be negative'),
                       t_0 - value_0));
    const output_0 = { nonce:
                         this._upgradeFromTransient_0(this._transientHash_0([__compactRuntime.convertBytesToUint(52435875175126190479447740508185965837690552500527637822603658699938581184512n,
                                                                                                                 28,
                                                                                                                 new Uint8Array([109, 105, 100, 110, 105, 103, 104, 116, 58, 107, 101, 114, 110, 101, 108, 58, 110, 111, 110, 99, 101, 95, 101, 118, 111, 108, 118, 101]),
                                                                                                                 'Field',
                                                                                                                 '<standard library>'),
                                                                             this._degradeToTransient_0(input_0.nonce)])),
                       color: input_0.color,
                       value: value_0 };
    this._createZswapOutput_0(context, partialProofData, output_0, recipient_0);
    const tmp_1 = this._coinCommitment_0(output_0, recipient_0);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { swap: { n: 0 } },
                                       { idx: { cached: true,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(2n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(tmp_1),
                                                                                              alignment: _descriptor_2.alignment() }).encode() } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newNull().encode() } },
                                       { ins: { cached: true, n: 2 } },
                                       { swap: { n: 0 } }]);
    if (!recipient_0.is_left
        &&
        this._equal_0(recipient_0.right.bytes, selfAddr_0.bytes))
    {
      const tmp_2 = this._coinCommitment_0(output_0, recipient_0);
      __compactRuntime.queryLedgerState(context,
                                        partialProofData,
                                        [
                                         { swap: { n: 0 } },
                                         { idx: { cached: true,
                                                  pushPath: true,
                                                  path: [
                                                         { tag: 'value',
                                                           value: { value: _descriptor_3.toValue(1n),
                                                                    alignment: _descriptor_3.alignment() } }] } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(tmp_2),
                                                                                                alignment: _descriptor_2.alignment() }).encode() } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newNull().encode() } },
                                         { ins: { cached: true, n: 2 } },
                                         { swap: { n: 0 } }]);
    }
    if (change_0 === 0n) {
      return { change: this._none_0(), sent: output_0 };
    } else {
      const changeCoin_0 = { nonce:
                               this._upgradeFromTransient_0(this._transientHash_0([__compactRuntime.convertBytesToUint(52435875175126190479447740508185965837690552500527637822603658699938581184512n,
                                                                                                                       30,
                                                                                                                       new Uint8Array([109, 105, 100, 110, 105, 103, 104, 116, 58, 107, 101, 114, 110, 101, 108, 58, 110, 111, 110, 99, 101, 95, 101, 118, 111, 108, 118, 101, 47, 50]),
                                                                                                                       'Field',
                                                                                                                       '<standard library>'),
                                                                                   this._degradeToTransient_0(input_0.nonce)])),
                             color: input_0.color,
                             value: change_0 };
      this._createZswapOutput_0(context,
                                partialProofData,
                                changeCoin_0,
                                this._right_0(selfAddr_0));
      const cm_0 = this._coinCommitment_0(changeCoin_0,
                                          this._right_0(selfAddr_0));
      __compactRuntime.queryLedgerState(context,
                                        partialProofData,
                                        [
                                         { swap: { n: 0 } },
                                         { idx: { cached: true,
                                                  pushPath: true,
                                                  path: [
                                                         { tag: 'value',
                                                           value: { value: _descriptor_3.toValue(2n),
                                                                    alignment: _descriptor_3.alignment() } }] } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(cm_0),
                                                                                                alignment: _descriptor_2.alignment() }).encode() } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newNull().encode() } },
                                         { ins: { cached: true, n: 2 } },
                                         { swap: { n: 0 } }]);
      __compactRuntime.queryLedgerState(context,
                                        partialProofData,
                                        [
                                         { swap: { n: 0 } },
                                         { idx: { cached: true,
                                                  pushPath: true,
                                                  path: [
                                                         { tag: 'value',
                                                           value: { value: _descriptor_3.toValue(1n),
                                                                    alignment: _descriptor_3.alignment() } }] } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(cm_0),
                                                                                                alignment: _descriptor_2.alignment() }).encode() } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newNull().encode() } },
                                         { ins: { cached: true, n: 2 } },
                                         { swap: { n: 0 } }]);
      return { change: this._some_0(changeCoin_0), sent: output_0 };
    }
  }
  _downcastQualifiedCoin_0(coin_0) {
    return { nonce: coin_0.nonce, color: coin_0.color, value: coin_0.value };
  }
  _coinCommitment_0(coin_0, recipient_0) {
    return this._persistentHash_1({ domain_sep:
                                      new Uint8Array([109, 105, 100, 110, 105, 103, 104, 116, 58, 122, 115, 119, 97, 112, 45, 99, 99, 91, 118, 49, 93]),
                                    info: coin_0,
                                    dataType: recipient_0.is_left,
                                    data:
                                      recipient_0.is_left ?
                                      recipient_0.left.bytes :
                                      recipient_0.right.bytes });
  }
  _coinNullifier_0(coin_0, addr_0) {
    return this._persistentHash_1({ domain_sep:
                                      new Uint8Array([109, 105, 100, 110, 105, 103, 104, 116, 58, 122, 115, 119, 97, 112, 45, 99, 110, 91, 118, 49, 93]),
                                    info: coin_0,
                                    dataType: false,
                                    data: addr_0.bytes });
  }
  async _blockTimeLt_0(context, partialProofData, time_0) {
    return _descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                     partialProofData,
                                                                     [
                                                                      { dup: { n: 2 } },
                                                                      { idx: { cached: true,
                                                                               pushPath: false,
                                                                               path: [
                                                                                      { tag: 'value',
                                                                                        value: { value: _descriptor_3.toValue(2n),
                                                                                                 alignment: _descriptor_3.alignment() } }] } },
                                                                      { push: { storage: false,
                                                                                value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(time_0),
                                                                                                                             alignment: _descriptor_0.alignment() }).encode() } },
                                                                      'lt',
                                                                      { popeq: { cached: true,
                                                                                 result: undefined } }]).value);
  }
  async _blockTimeGte_0(context, partialProofData, time_0) {
    return !await this._blockTimeLt_0(context, partialProofData, time_0);
  }
  _transientHash_0(value_0) {
    const result_0 = __compactRuntime.transientHash(_descriptor_16, value_0);
    return result_0;
  }
  _persistentHash_0(value_0) {
    const result_0 = __compactRuntime.persistentHash(_descriptor_13, value_0);
    return result_0;
  }
  _persistentHash_1(value_0) {
    const result_0 = __compactRuntime.persistentHash(_descriptor_15, value_0);
    return result_0;
  }
  _degradeToTransient_0(x_0) {
    const result_0 = __compactRuntime.degradeToTransient(x_0);
    return result_0;
  }
  _upgradeFromTransient_0(x_0) {
    const result_0 = __compactRuntime.upgradeFromTransient(x_0);
    return result_0;
  }
  _createZswapInput_0(context, partialProofData, coin_0) {
    const result_0 = __compactRuntime.createZswapInput(context, coin_0);
    partialProofData.privateTranscriptOutputs.push({
      value: [],
      alignment: []
    });
    return result_0;
  }
  _createZswapOutput_0(context, partialProofData, coin_0, recipient_0) {
    const result_0 = __compactRuntime.createZswapOutput(context,
                                                        coin_0,
                                                        recipient_0);
    partialProofData.privateTranscriptOutputs.push({
      value: [],
      alignment: []
    });
    return result_0;
  }
  _agentSecretKey_0(context, partialProofData) {
    const witnessContext_0 = __compactRuntime.createWitnessContext(ledger(context.callContext.currentQueryContext.state), context.callContext.currentPrivateState, context.callContext.currentQueryContext.address);
    const [nextPrivateState_0, result_0] = this.witnesses.agentSecretKey(witnessContext_0);
    context.callContext.currentPrivateState = nextPrivateState_0;
    if (!(result_0.buffer instanceof ArrayBuffer && result_0.BYTES_PER_ELEMENT === 1 && result_0.length === 32)) {
      __compactRuntime.typeError('agentSecretKey',
                                 'return value',
                                 'escrow.compact line 60 char 1',
                                 'Bytes<32>',
                                 result_0)
    }
    partialProofData.privateTranscriptOutputs.push({
      value: _descriptor_2.toValue(result_0),
      alignment: _descriptor_2.alignment()
    });
    return result_0;
  }
  _organizerSecretKey_0(context, partialProofData) {
    const witnessContext_0 = __compactRuntime.createWitnessContext(ledger(context.callContext.currentQueryContext.state), context.callContext.currentPrivateState, context.callContext.currentQueryContext.address);
    const [nextPrivateState_0, result_0] = this.witnesses.organizerSecretKey(witnessContext_0);
    context.callContext.currentPrivateState = nextPrivateState_0;
    if (!(result_0.buffer instanceof ArrayBuffer && result_0.BYTES_PER_ELEMENT === 1 && result_0.length === 32)) {
      __compactRuntime.typeError('organizerSecretKey',
                                 'return value',
                                 'escrow.compact line 61 char 1',
                                 'Bytes<32>',
                                 result_0)
    }
    partialProofData.privateTranscriptOutputs.push({
      value: _descriptor_2.toValue(result_0),
      alignment: _descriptor_2.alignment()
    });
    return result_0;
  }
  _agentCommitment_0(sk_0) {
    return this._persistentHash_0([new Uint8Array([101, 118, 101, 114, 108, 105, 115, 116, 58, 97, 103, 101, 110, 116, 58, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                                   sk_0]);
  }
  _organizerCommitment_0(sk_0) {
    return this._persistentHash_0([new Uint8Array([101, 118, 101, 114, 108, 105, 115, 116, 58, 111, 114, 103, 97, 110, 105, 122, 101, 114, 58, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                                   sk_0]);
  }
  async _createEscrow_0(context,
                        partialProofData,
                        amount_0,
                        organizerCommitmentInput_0,
                        bookingRef_0,
                        deadline_0,
                        claimDeadline_0,
                        deposit_0,
                        agentPk_0,
                        organizerPk_0)
  {
    __compactRuntime.assert(amount_0 > 0n, 'amount must be positive');
    __compactRuntime.assert(deposit_0.value === amount_0,
                            'deposit must equal escrow amount');
    __compactRuntime.assert(claimDeadline_0 > deadline_0,
                            'claim deadline must be after refund deadline');
    await this._receiveShielded_0(context, partialProofData, deposit_0);
    const tmp_0 = 1n;
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(1n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { addi: { immediate: parseInt(__compactRuntime.valueToBigInt(
                                                              { value: _descriptor_8.toValue(tmp_0),
                                                                alignment: _descriptor_8.alignment() }
                                                                .value
                                                            )) } },
                                       { ins: { cached: true, n: 1 } }]);
    const id_0 = _descriptor_0.fromValue(__compactRuntime.queryLedgerState(context,
                                                                           partialProofData,
                                                                           [
                                                                            { dup: { n: 0 } },
                                                                            { idx: { cached: false,
                                                                                     pushPath: false,
                                                                                     path: [
                                                                                            { tag: 'value',
                                                                                              value: { value: _descriptor_3.toValue(1n),
                                                                                                       alignment: _descriptor_3.alignment() } }] } },
                                                                            { popeq: { cached: true,
                                                                                       result: undefined } }]).value);
    const aComm_0 = this._agentCommitment_0(this._agentSecretKey_0(context,
                                                                   partialProofData));
    const tmp_1 = { amount: amount_0,
                    agentCommitment: aComm_0,
                    organizerCommitment: organizerCommitmentInput_0,
                    state: 1n,
                    bookingRef: bookingRef_0,
                    deadline: deadline_0,
                    claimDeadline: claimDeadline_0,
                    coinNonce: deposit_0.nonce,
                    coinColor: deposit_0.color };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(0n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(2n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_6.toValue(agentPk_0),
                                                                                              alignment: _descriptor_6.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(3n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_6.toValue(organizerPk_0),
                                                                                              alignment: _descriptor_6.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _releaseEscrow_0(context, partialProofData, escrowId_0, spendCoin_0) {
    const id_0 = escrowId_0;
    __compactRuntime.assert(_descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                      partialProofData,
                                                                                      [
                                                                                       { dup: { n: 0 } },
                                                                                       { idx: { cached: false,
                                                                                                pushPath: false,
                                                                                                path: [
                                                                                                       { tag: 'value',
                                                                                                         value: { value: _descriptor_3.toValue(0n),
                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                       { push: { storage: false,
                                                                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                                                                       'member',
                                                                                       { popeq: { cached: true,
                                                                                                  result: undefined } }]).value),
                            'escrow not found');
    const e_0 = _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_3.toValue(0n),
                                                                                                      alignment: _descriptor_3.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(id_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(e_0.state === 1n, 'escrow not in HELD state');
    const caller_0 = this._organizerCommitment_0(this._organizerSecretKey_0(context,
                                                                            partialProofData));
    __compactRuntime.assert(this._equal_1(caller_0, e_0.organizerCommitment),
                            'only organizer can release');
    __compactRuntime.assert(this._equal_2(spendCoin_0.nonce, e_0.coinNonce),
                            'coin does not match escrow custody');
    __compactRuntime.assert(this._equal_3(spendCoin_0.color, e_0.coinColor),
                            'coin does not match escrow custody');
    __compactRuntime.assert(spendCoin_0.value === e_0.amount,
                            'coin does not match escrow custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(_descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                                      partialProofData,
                                                                                                      [
                                                                                                       { dup: { n: 0 } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_3.toValue(3n),
                                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_0.toValue(id_0),
                                                                                                                                  alignment: _descriptor_0.alignment() } }] } },
                                                                                                       { popeq: { cached: false,
                                                                                                                  result: undefined } }]).value)),
                               e_0.amount);
    const tmp_0 = { amount: e_0.amount,
                    agentCommitment: e_0.agentCommitment,
                    organizerCommitment: e_0.organizerCommitment,
                    state: 2n,
                    bookingRef: e_0.bookingRef,
                    deadline: e_0.deadline,
                    claimDeadline: e_0.claimDeadline,
                    coinNonce: e_0.coinNonce,
                    coinColor: e_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(0n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_0),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _refundEscrow_0(context, partialProofData, escrowId_0, spendCoin_0) {
    const id_0 = escrowId_0;
    __compactRuntime.assert(_descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                      partialProofData,
                                                                                      [
                                                                                       { dup: { n: 0 } },
                                                                                       { idx: { cached: false,
                                                                                                pushPath: false,
                                                                                                path: [
                                                                                                       { tag: 'value',
                                                                                                         value: { value: _descriptor_3.toValue(0n),
                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                       { push: { storage: false,
                                                                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                                                                       'member',
                                                                                       { popeq: { cached: true,
                                                                                                  result: undefined } }]).value),
                            'escrow not found');
    const e_0 = _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_3.toValue(0n),
                                                                                                      alignment: _descriptor_3.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(id_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(e_0.state === 1n, 'escrow not in HELD state');
    const caller_0 = this._agentCommitment_0(this._agentSecretKey_0(context,
                                                                    partialProofData));
    __compactRuntime.assert(this._equal_4(caller_0, e_0.agentCommitment),
                            'only agent can refund');
    __compactRuntime.assert(!await this._blockTimeGte_0(context,
                                                        partialProofData,
                                                        e_0.claimDeadline),
                            'claim deadline passed - merchant auto-release applies');
    __compactRuntime.assert(this._equal_5(spendCoin_0.nonce, e_0.coinNonce),
                            'coin does not match escrow custody');
    __compactRuntime.assert(this._equal_6(spendCoin_0.color, e_0.coinColor),
                            'coin does not match escrow custody');
    __compactRuntime.assert(spendCoin_0.value === e_0.amount,
                            'coin does not match escrow custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(_descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                                      partialProofData,
                                                                                                      [
                                                                                                       { dup: { n: 0 } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_3.toValue(2n),
                                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_0.toValue(id_0),
                                                                                                                                  alignment: _descriptor_0.alignment() } }] } },
                                                                                                       { popeq: { cached: false,
                                                                                                                  result: undefined } }]).value)),
                               e_0.amount);
    const tmp_0 = { amount: e_0.amount,
                    agentCommitment: e_0.agentCommitment,
                    organizerCommitment: e_0.organizerCommitment,
                    state: 3n,
                    bookingRef: e_0.bookingRef,
                    deadline: e_0.deadline,
                    claimDeadline: e_0.claimDeadline,
                    coinNonce: e_0.coinNonce,
                    coinColor: e_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(0n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_0),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _timeoutRefund_0(context, partialProofData, escrowId_0, spendCoin_0) {
    const id_0 = escrowId_0;
    __compactRuntime.assert(_descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                      partialProofData,
                                                                                      [
                                                                                       { dup: { n: 0 } },
                                                                                       { idx: { cached: false,
                                                                                                pushPath: false,
                                                                                                path: [
                                                                                                       { tag: 'value',
                                                                                                         value: { value: _descriptor_3.toValue(0n),
                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                       { push: { storage: false,
                                                                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                                                                       'member',
                                                                                       { popeq: { cached: true,
                                                                                                  result: undefined } }]).value),
                            'escrow not found');
    const e_0 = _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_3.toValue(0n),
                                                                                                      alignment: _descriptor_3.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(id_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(e_0.state === 1n, 'escrow not in HELD state');
    __compactRuntime.assert(await this._blockTimeGte_0(context,
                                                       partialProofData,
                                                       e_0.deadline),
                            'deadline not reached yet');
    __compactRuntime.assert(!await this._blockTimeGte_0(context,
                                                        partialProofData,
                                                        e_0.claimDeadline),
                            'claim deadline passed - merchant auto-release applies');
    __compactRuntime.assert(this._equal_7(spendCoin_0.nonce, e_0.coinNonce),
                            'coin does not match escrow custody');
    __compactRuntime.assert(this._equal_8(spendCoin_0.color, e_0.coinColor),
                            'coin does not match escrow custody');
    __compactRuntime.assert(spendCoin_0.value === e_0.amount,
                            'coin does not match escrow custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(_descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                                      partialProofData,
                                                                                                      [
                                                                                                       { dup: { n: 0 } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_3.toValue(2n),
                                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_0.toValue(id_0),
                                                                                                                                  alignment: _descriptor_0.alignment() } }] } },
                                                                                                       { popeq: { cached: false,
                                                                                                                  result: undefined } }]).value)),
                               e_0.amount);
    const tmp_0 = { amount: e_0.amount,
                    agentCommitment: e_0.agentCommitment,
                    organizerCommitment: e_0.organizerCommitment,
                    state: 3n,
                    bookingRef: e_0.bookingRef,
                    deadline: e_0.deadline,
                    claimDeadline: e_0.claimDeadline,
                    coinNonce: e_0.coinNonce,
                    coinColor: e_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(0n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_0),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _mutualRefund_0(context, partialProofData, escrowId_0, returnCoin_0) {
    const id_0 = escrowId_0;
    __compactRuntime.assert(_descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                      partialProofData,
                                                                                      [
                                                                                       { dup: { n: 0 } },
                                                                                       { idx: { cached: false,
                                                                                                pushPath: false,
                                                                                                path: [
                                                                                                       { tag: 'value',
                                                                                                         value: { value: _descriptor_3.toValue(0n),
                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                       { push: { storage: false,
                                                                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                                                                       'member',
                                                                                       { popeq: { cached: true,
                                                                                                  result: undefined } }]).value),
                            'escrow not found');
    const e_0 = _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_3.toValue(0n),
                                                                                                      alignment: _descriptor_3.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(id_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(e_0.state === 2n, 'escrow not in RELEASED state');
    const callerAgent_0 = this._agentCommitment_0(this._agentSecretKey_0(context,
                                                                         partialProofData));
    __compactRuntime.assert(this._equal_9(callerAgent_0, e_0.agentCommitment),
                            'agent consent missing');
    const callerOrg_0 = this._organizerCommitment_0(this._organizerSecretKey_0(context,
                                                                               partialProofData));
    __compactRuntime.assert(this._equal_10(callerOrg_0, e_0.organizerCommitment),
                            'organizer consent missing');
    __compactRuntime.assert(this._equal_11(returnCoin_0.color, e_0.coinColor),
                            'return coin wrong asset');
    __compactRuntime.assert(returnCoin_0.value === e_0.amount,
                            'return coin wrong amount');
    await this._receiveShielded_0(context,
                                  partialProofData,
                                  { nonce: returnCoin_0.nonce,
                                    color: returnCoin_0.color,
                                    value: returnCoin_0.value });
    await this._sendShielded_0(context,
                               partialProofData,
                               returnCoin_0,
                               this._left_0(_descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                                      partialProofData,
                                                                                                      [
                                                                                                       { dup: { n: 0 } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_3.toValue(2n),
                                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_0.toValue(id_0),
                                                                                                                                  alignment: _descriptor_0.alignment() } }] } },
                                                                                                       { popeq: { cached: false,
                                                                                                                  result: undefined } }]).value)),
                               e_0.amount);
    const tmp_0 = { amount: e_0.amount,
                    agentCommitment: e_0.agentCommitment,
                    organizerCommitment: e_0.organizerCommitment,
                    state: 3n,
                    bookingRef: e_0.bookingRef,
                    deadline: e_0.deadline,
                    claimDeadline: e_0.claimDeadline,
                    coinNonce: e_0.coinNonce,
                    coinColor: e_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(0n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_0),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _autoRelease_0(context, partialProofData, escrowId_0, spendCoin_0) {
    const id_0 = escrowId_0;
    __compactRuntime.assert(_descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                      partialProofData,
                                                                                      [
                                                                                       { dup: { n: 0 } },
                                                                                       { idx: { cached: false,
                                                                                                pushPath: false,
                                                                                                path: [
                                                                                                       { tag: 'value',
                                                                                                         value: { value: _descriptor_3.toValue(0n),
                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                       { push: { storage: false,
                                                                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                                                                       'member',
                                                                                       { popeq: { cached: true,
                                                                                                  result: undefined } }]).value),
                            'escrow not found');
    const e_0 = _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_3.toValue(0n),
                                                                                                      alignment: _descriptor_3.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(id_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(e_0.state === 1n, 'escrow not in HELD state');
    __compactRuntime.assert(await this._blockTimeGte_0(context,
                                                       partialProofData,
                                                       e_0.claimDeadline),
                            'claim deadline not reached yet');
    __compactRuntime.assert(this._equal_12(spendCoin_0.nonce, e_0.coinNonce),
                            'coin does not match escrow custody');
    __compactRuntime.assert(this._equal_13(spendCoin_0.color, e_0.coinColor),
                            'coin does not match escrow custody');
    __compactRuntime.assert(spendCoin_0.value === e_0.amount,
                            'coin does not match escrow custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(_descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                                      partialProofData,
                                                                                                      [
                                                                                                       { dup: { n: 0 } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_3.toValue(3n),
                                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                                       { idx: { cached: false,
                                                                                                                pushPath: false,
                                                                                                                path: [
                                                                                                                       { tag: 'value',
                                                                                                                         value: { value: _descriptor_0.toValue(id_0),
                                                                                                                                  alignment: _descriptor_0.alignment() } }] } },
                                                                                                       { popeq: { cached: false,
                                                                                                                  result: undefined } }]).value)),
                               e_0.amount);
    const tmp_0 = { amount: e_0.amount,
                    agentCommitment: e_0.agentCommitment,
                    organizerCommitment: e_0.organizerCommitment,
                    state: 2n,
                    bookingRef: e_0.bookingRef,
                    deadline: e_0.deadline,
                    claimDeadline: e_0.claimDeadline,
                    coinNonce: e_0.coinNonce,
                    coinColor: e_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_3.toValue(0n),
                                                                  alignment: _descriptor_3.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_0),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _isHeld_0(context, partialProofData, escrowId_0) {
    const id_0 = escrowId_0;
    __compactRuntime.assert(_descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                      partialProofData,
                                                                                      [
                                                                                       { dup: { n: 0 } },
                                                                                       { idx: { cached: false,
                                                                                                pushPath: false,
                                                                                                path: [
                                                                                                       { tag: 'value',
                                                                                                         value: { value: _descriptor_3.toValue(0n),
                                                                                                                  alignment: _descriptor_3.alignment() } }] } },
                                                                                       { push: { storage: false,
                                                                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(id_0),
                                                                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                                                                       'member',
                                                                                       { popeq: { cached: true,
                                                                                                  result: undefined } }]).value),
                            'escrow not found');
    const e_0 = _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_3.toValue(0n),
                                                                                                      alignment: _descriptor_3.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(id_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    return e_0.state === 1n;
  }
  _equal_0(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_1(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_2(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_3(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_4(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_5(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_6(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_7(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_8(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_9(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_10(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_11(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_12(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_13(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
}
export function ledger(stateOrChargedState) {
  const state = stateOrChargedState instanceof __compactRuntime.StateValue ? stateOrChargedState : stateOrChargedState.state;
  const chargedState = stateOrChargedState instanceof __compactRuntime.StateValue ? new __compactRuntime.ChargedState(stateOrChargedState) : stateOrChargedState;
  const context = {
    callContext: { currentQueryContext: new __compactRuntime.QueryContext(chargedState, __compactRuntime.dummyContractAddress()), currentGasCost: __compactRuntime.emptyRunningCost() },
    costModel: __compactRuntime.CostModel.initialCostModel()
  };
  const partialProofData = {
    input: { value: [], alignment: [] },
    output: undefined,
    publicTranscript: [],
    privateTranscriptOutputs: []
  };
  return {
    escrows: {
      isEmpty(...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`isEmpty: expected 0 arguments, received ${args_0.length}`);
        }
        return _descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(0n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          'size',
                                                                          { push: { storage: false,
                                                                                    value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(0n),
                                                                                                                                 alignment: _descriptor_0.alignment() }).encode() } },
                                                                          'eq',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      size(...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`size: expected 0 arguments, received ${args_0.length}`);
        }
        return _descriptor_0.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(0n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          'size',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      member(...args_0) {
        if (args_0.length !== 1) {
          throw new __compactRuntime.CompactError(`member: expected 1 argument, received ${args_0.length}`);
        }
        const key_0 = args_0[0];
        if (!(typeof(key_0) === 'bigint' && key_0 >= 0n && key_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('member',
                                     'argument 1',
                                     'escrow.compact line 55 char 1',
                                     'Uint<0..18446744073709551616>',
                                     key_0)
        }
        return _descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(0n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          { push: { storage: false,
                                                                                    value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(key_0),
                                                                                                                                 alignment: _descriptor_0.alignment() }).encode() } },
                                                                          'member',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      lookup(...args_0) {
        if (args_0.length !== 1) {
          throw new __compactRuntime.CompactError(`lookup: expected 1 argument, received ${args_0.length}`);
        }
        const key_0 = args_0[0];
        if (!(typeof(key_0) === 'bigint' && key_0 >= 0n && key_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('lookup',
                                     'argument 1',
                                     'escrow.compact line 55 char 1',
                                     'Uint<0..18446744073709551616>',
                                     key_0)
        }
        return _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(0n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_0.toValue(key_0),
                                                                                                     alignment: _descriptor_0.alignment() } }] } },
                                                                          { popeq: { cached: false,
                                                                                     result: undefined } }]).value);
      },
      [Symbol.iterator](...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`iter: expected 0 arguments, received ${args_0.length}`);
        }
        const self_0 = state.asArray()[0];
        return self_0.asMap().keys().map(  (key) => {    const value = self_0.asMap().get(key).asCell();    return [      _descriptor_0.fromValue(key.value),      _descriptor_4.fromValue(value.value)    ];  })[Symbol.iterator]();
      }
    },
    get nextId() {
      return _descriptor_0.fromValue(__compactRuntime.queryLedgerState(context,
                                                                       partialProofData,
                                                                       [
                                                                        { dup: { n: 0 } },
                                                                        { idx: { cached: false,
                                                                                 pushPath: false,
                                                                                 path: [
                                                                                        { tag: 'value',
                                                                                          value: { value: _descriptor_3.toValue(1n),
                                                                                                   alignment: _descriptor_3.alignment() } }] } },
                                                                        { popeq: { cached: true,
                                                                                   result: undefined } }]).value);
    },
    agentPks: {
      isEmpty(...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`isEmpty: expected 0 arguments, received ${args_0.length}`);
        }
        return _descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(2n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          'size',
                                                                          { push: { storage: false,
                                                                                    value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(0n),
                                                                                                                                 alignment: _descriptor_0.alignment() }).encode() } },
                                                                          'eq',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      size(...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`size: expected 0 arguments, received ${args_0.length}`);
        }
        return _descriptor_0.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(2n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          'size',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      member(...args_0) {
        if (args_0.length !== 1) {
          throw new __compactRuntime.CompactError(`member: expected 1 argument, received ${args_0.length}`);
        }
        const key_0 = args_0[0];
        if (!(typeof(key_0) === 'bigint' && key_0 >= 0n && key_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('member',
                                     'argument 1',
                                     'escrow.compact line 57 char 1',
                                     'Uint<0..18446744073709551616>',
                                     key_0)
        }
        return _descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(2n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          { push: { storage: false,
                                                                                    value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(key_0),
                                                                                                                                 alignment: _descriptor_0.alignment() }).encode() } },
                                                                          'member',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      lookup(...args_0) {
        if (args_0.length !== 1) {
          throw new __compactRuntime.CompactError(`lookup: expected 1 argument, received ${args_0.length}`);
        }
        const key_0 = args_0[0];
        if (!(typeof(key_0) === 'bigint' && key_0 >= 0n && key_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('lookup',
                                     'argument 1',
                                     'escrow.compact line 57 char 1',
                                     'Uint<0..18446744073709551616>',
                                     key_0)
        }
        return _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(2n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_0.toValue(key_0),
                                                                                                     alignment: _descriptor_0.alignment() } }] } },
                                                                          { popeq: { cached: false,
                                                                                     result: undefined } }]).value);
      },
      [Symbol.iterator](...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`iter: expected 0 arguments, received ${args_0.length}`);
        }
        const self_0 = state.asArray()[2];
        return self_0.asMap().keys().map(  (key) => {    const value = self_0.asMap().get(key).asCell();    return [      _descriptor_0.fromValue(key.value),      _descriptor_6.fromValue(value.value)    ];  })[Symbol.iterator]();
      }
    },
    organizerPks: {
      isEmpty(...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`isEmpty: expected 0 arguments, received ${args_0.length}`);
        }
        return _descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(3n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          'size',
                                                                          { push: { storage: false,
                                                                                    value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(0n),
                                                                                                                                 alignment: _descriptor_0.alignment() }).encode() } },
                                                                          'eq',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      size(...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`size: expected 0 arguments, received ${args_0.length}`);
        }
        return _descriptor_0.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(3n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          'size',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      member(...args_0) {
        if (args_0.length !== 1) {
          throw new __compactRuntime.CompactError(`member: expected 1 argument, received ${args_0.length}`);
        }
        const key_0 = args_0[0];
        if (!(typeof(key_0) === 'bigint' && key_0 >= 0n && key_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('member',
                                     'argument 1',
                                     'escrow.compact line 58 char 1',
                                     'Uint<0..18446744073709551616>',
                                     key_0)
        }
        return _descriptor_5.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(3n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          { push: { storage: false,
                                                                                    value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(key_0),
                                                                                                                                 alignment: _descriptor_0.alignment() }).encode() } },
                                                                          'member',
                                                                          { popeq: { cached: true,
                                                                                     result: undefined } }]).value);
      },
      lookup(...args_0) {
        if (args_0.length !== 1) {
          throw new __compactRuntime.CompactError(`lookup: expected 1 argument, received ${args_0.length}`);
        }
        const key_0 = args_0[0];
        if (!(typeof(key_0) === 'bigint' && key_0 >= 0n && key_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('lookup',
                                     'argument 1',
                                     'escrow.compact line 58 char 1',
                                     'Uint<0..18446744073709551616>',
                                     key_0)
        }
        return _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_3.toValue(3n),
                                                                                                     alignment: _descriptor_3.alignment() } }] } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_0.toValue(key_0),
                                                                                                     alignment: _descriptor_0.alignment() } }] } },
                                                                          { popeq: { cached: false,
                                                                                     result: undefined } }]).value);
      },
      [Symbol.iterator](...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`iter: expected 0 arguments, received ${args_0.length}`);
        }
        const self_0 = state.asArray()[3];
        return self_0.asMap().keys().map(  (key) => {    const value = self_0.asMap().get(key).asCell();    return [      _descriptor_0.fromValue(key.value),      _descriptor_6.fromValue(value.value)    ];  })[Symbol.iterator]();
      }
    }
  };
}
const _emptyContext = {
  callContext: { currentQueryContext: new __compactRuntime.QueryContext(new __compactRuntime.ContractState().data, __compactRuntime.dummyContractAddress()), currentGasCost: __compactRuntime.emptyRunningCost() }
};
const _dummyContract = new Contract({
  agentSecretKey: (...args) => undefined,
  organizerSecretKey: (...args) => undefined
});
export const pureCircuits = {
  agentCommitment: (...args_0) => {
    if (args_0.length !== 1) {
      throw new __compactRuntime.CompactError(`agentCommitment: expected 1 argument (as invoked from Typescript), received ${args_0.length}`);
    }
    const sk_0 = args_0[0];
    if (!(sk_0.buffer instanceof ArrayBuffer && sk_0.BYTES_PER_ELEMENT === 1 && sk_0.length === 32)) {
      __compactRuntime.typeError('agentCommitment',
                                 'argument 1',
                                 'escrow.compact line 64 char 1',
                                 'Bytes<32>',
                                 sk_0)
    }
    return _dummyContract._agentCommitment_0(sk_0);
  },
  organizerCommitment: (...args_0) => {
    if (args_0.length !== 1) {
      throw new __compactRuntime.CompactError(`organizerCommitment: expected 1 argument (as invoked from Typescript), received ${args_0.length}`);
    }
    const sk_0 = args_0[0];
    if (!(sk_0.buffer instanceof ArrayBuffer && sk_0.BYTES_PER_ELEMENT === 1 && sk_0.length === 32)) {
      __compactRuntime.typeError('organizerCommitment',
                                 'argument 1',
                                 'escrow.compact line 69 char 1',
                                 'Bytes<32>',
                                 sk_0)
    }
    return _dummyContract._organizerCommitment_0(sk_0);
  }
};
export const contractReferenceLocations =
  { tag: 'publicLedgerArray', indices: { } };
export const expectedVk = {
  'autoRelease': 'f842a867731250008b358daa00f07fda34be4c621641317d1901d07d23be05e7',
  'createEscrow': 'a6435732f0997a749d3956cbf557474a562ef2612b4b98b0c82b48810688e351',
  'isHeld': '5c0969dc67c8de2bb4f179e70c9f30b2b54a53b8a8260a4c58ea637ae9e0f0d5',
  'mutualRefund': 'af19abb2aafda6f6199f5f25ce3fdb05c7b61be447be481155e8f6e8b236fb83',
  'refundEscrow': 'a476191469b4ff75631ef2b49bc95d54e7d858c05882cd766f49a89a058e9d28',
  'releaseEscrow': 'b3546f683e23099fd53ad19b3ad01222683a8e00178948e0ccbdc5d095f54c98',
  'timeoutRefund': '9e4cf3d298a7955ccd1399529557fbbb4bd3c5989f892ee87c8f577a68e98af4',
};

//# sourceMappingURL=index.js.map
