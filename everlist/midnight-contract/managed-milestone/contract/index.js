import * as __compactRuntime from '@midnight-ntwrk/compact-runtime';
__compactRuntime.checkRuntimeVersion('0.19.0');

const _descriptor_0 = new __compactRuntime.CompactTypeUnsignedInteger(18446744073709551615n, 8);

const _descriptor_1 = new __compactRuntime.CompactTypeUnsignedInteger(340282366920938463463374607431768211455n, 16);

const _descriptor_2 = new __compactRuntime.CompactTypeUnsignedInteger(255n, 1);

const _descriptor_3 = new __compactRuntime.CompactTypeBytes(32);

class _Milestone_0 {
  alignment() {
    return _descriptor_1.alignment().concat(_descriptor_2.alignment().concat(_descriptor_0.alignment().concat(_descriptor_0.alignment().concat(_descriptor_3.alignment().concat(_descriptor_3.alignment())))));
  }
  fromValue(value_0) {
    return {
      amount: _descriptor_1.fromValue(value_0),
      state: _descriptor_2.fromValue(value_0),
      deadline: _descriptor_0.fromValue(value_0),
      claimDeadline: _descriptor_0.fromValue(value_0),
      coinNonce: _descriptor_3.fromValue(value_0),
      coinColor: _descriptor_3.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_1.toValue(value_0.amount).concat(_descriptor_2.toValue(value_0.state).concat(_descriptor_0.toValue(value_0.deadline).concat(_descriptor_0.toValue(value_0.claimDeadline).concat(_descriptor_3.toValue(value_0.coinNonce).concat(_descriptor_3.toValue(value_0.coinColor))))));
  }
}

const _descriptor_4 = new _Milestone_0();

class _ZswapCoinPublicKey_0 {
  alignment() {
    return _descriptor_3.alignment();
  }
  fromValue(value_0) {
    return {
      bytes: _descriptor_3.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_3.toValue(value_0.bytes);
  }
}

const _descriptor_5 = new _ZswapCoinPublicKey_0();

class _Deal_0 {
  alignment() {
    return _descriptor_3.alignment().concat(_descriptor_3.alignment().concat(_descriptor_3.alignment().concat(_descriptor_3.alignment().concat(_descriptor_2.alignment().concat(_descriptor_2.alignment().concat(_descriptor_0.alignment().concat(_descriptor_5.alignment().concat(_descriptor_5.alignment()))))))));
  }
  fromValue(value_0) {
    return {
      dealRef: _descriptor_3.fromValue(value_0),
      agentCommitment: _descriptor_3.fromValue(value_0),
      organizerCommitment: _descriptor_3.fromValue(value_0),
      arbiterCommitment: _descriptor_3.fromValue(value_0),
      count: _descriptor_2.fromValue(value_0),
      created: _descriptor_2.fromValue(value_0),
      arbiterDeadline: _descriptor_0.fromValue(value_0),
      agentPk: _descriptor_5.fromValue(value_0),
      organizerPk: _descriptor_5.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_3.toValue(value_0.dealRef).concat(_descriptor_3.toValue(value_0.agentCommitment).concat(_descriptor_3.toValue(value_0.organizerCommitment).concat(_descriptor_3.toValue(value_0.arbiterCommitment).concat(_descriptor_2.toValue(value_0.count).concat(_descriptor_2.toValue(value_0.created).concat(_descriptor_0.toValue(value_0.arbiterDeadline).concat(_descriptor_5.toValue(value_0.agentPk).concat(_descriptor_5.toValue(value_0.organizerPk)))))))));
  }
}

const _descriptor_6 = new _Deal_0();

class _QualifiedShieldedCoinInfo_0 {
  alignment() {
    return _descriptor_3.alignment().concat(_descriptor_3.alignment().concat(_descriptor_1.alignment().concat(_descriptor_0.alignment())));
  }
  fromValue(value_0) {
    return {
      nonce: _descriptor_3.fromValue(value_0),
      color: _descriptor_3.fromValue(value_0),
      value: _descriptor_1.fromValue(value_0),
      mt_index: _descriptor_0.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_3.toValue(value_0.nonce).concat(_descriptor_3.toValue(value_0.color).concat(_descriptor_1.toValue(value_0.value).concat(_descriptor_0.toValue(value_0.mt_index))));
  }
}

const _descriptor_7 = new _QualifiedShieldedCoinInfo_0();

const _descriptor_8 = __compactRuntime.CompactTypeBoolean;

class _ShieldedCoinInfo_0 {
  alignment() {
    return _descriptor_3.alignment().concat(_descriptor_3.alignment().concat(_descriptor_1.alignment()));
  }
  fromValue(value_0) {
    return {
      nonce: _descriptor_3.fromValue(value_0),
      color: _descriptor_3.fromValue(value_0),
      value: _descriptor_1.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_3.toValue(value_0.nonce).concat(_descriptor_3.toValue(value_0.color).concat(_descriptor_1.toValue(value_0.value)));
  }
}

const _descriptor_9 = new _ShieldedCoinInfo_0();

const _descriptor_10 = new __compactRuntime.CompactTypeUnsignedInteger(65535n, 2);

class _ContractAddress_0 {
  alignment() {
    return _descriptor_3.alignment();
  }
  fromValue(value_0) {
    return {
      bytes: _descriptor_3.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_3.toValue(value_0.bytes);
  }
}

const _descriptor_11 = new _ContractAddress_0();

class _Either_0 {
  alignment() {
    return _descriptor_8.alignment().concat(_descriptor_5.alignment().concat(_descriptor_11.alignment()));
  }
  fromValue(value_0) {
    return {
      is_left: _descriptor_8.fromValue(value_0),
      left: _descriptor_5.fromValue(value_0),
      right: _descriptor_11.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_8.toValue(value_0.is_left).concat(_descriptor_5.toValue(value_0.left).concat(_descriptor_11.toValue(value_0.right)));
  }
}

const _descriptor_12 = new _Either_0();

const _descriptor_13 = __compactRuntime.CompactTypeField;

const _descriptor_14 = new __compactRuntime.CompactTypeVector(3, _descriptor_3);

const _descriptor_15 = new __compactRuntime.CompactTypeBytes(21);

class _CoinPreimage_0 {
  alignment() {
    return _descriptor_15.alignment().concat(_descriptor_9.alignment().concat(_descriptor_8.alignment().concat(_descriptor_3.alignment())));
  }
  fromValue(value_0) {
    return {
      domain_sep: _descriptor_15.fromValue(value_0),
      info: _descriptor_9.fromValue(value_0),
      dataType: _descriptor_8.fromValue(value_0),
      data: _descriptor_3.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_15.toValue(value_0.domain_sep).concat(_descriptor_9.toValue(value_0.info).concat(_descriptor_8.toValue(value_0.dataType).concat(_descriptor_3.toValue(value_0.data))));
  }
}

const _descriptor_16 = new _CoinPreimage_0();

const _descriptor_17 = new __compactRuntime.CompactTypeVector(2, _descriptor_13);

class _Maybe_0 {
  alignment() {
    return _descriptor_8.alignment().concat(_descriptor_9.alignment());
  }
  fromValue(value_0) {
    return {
      is_some: _descriptor_8.fromValue(value_0),
      value: _descriptor_9.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_8.toValue(value_0.is_some).concat(_descriptor_9.toValue(value_0.value));
  }
}

const _descriptor_18 = new _Maybe_0();

class _ShieldedSendResult_0 {
  alignment() {
    return _descriptor_18.alignment().concat(_descriptor_9.alignment());
  }
  fromValue(value_0) {
    return {
      change: _descriptor_18.fromValue(value_0),
      sent: _descriptor_9.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_18.toValue(value_0.change).concat(_descriptor_9.toValue(value_0.sent));
  }
}

const _descriptor_19 = new _ShieldedSendResult_0();

class _Either_1 {
  alignment() {
    return _descriptor_8.alignment().concat(_descriptor_3.alignment().concat(_descriptor_3.alignment()));
  }
  fromValue(value_0) {
    return {
      is_left: _descriptor_8.fromValue(value_0),
      left: _descriptor_3.fromValue(value_0),
      right: _descriptor_3.fromValue(value_0)
    }
  }
  toValue(value_0) {
    return _descriptor_8.toValue(value_0.is_left).concat(_descriptor_3.toValue(value_0.left).concat(_descriptor_3.toValue(value_0.right)));
  }
}

const _descriptor_20 = new _Either_1();

const _descriptor_21 = new __compactRuntime.CompactTypeUnsignedInteger(4294967295n, 4);

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
    if (typeof(witnesses_0.arbiterSecretKey) !== 'function') {
      throw new __compactRuntime.CompactError('first (witnesses) argument to Contract constructor does not contain a function-valued field named arbiterSecretKey');
    }
    this.witnesses = witnesses_0;
    this.circuits = {
      async agentCommitment(context, ...args_1) {
        return { result: pureCircuits.agentCommitment(...args_1), context };
      },
      async organizerCommitment(context, ...args_1) {
        return { result: pureCircuits.organizerCommitment(...args_1), context };
      },
      async arbiterCommitment(context, ...args_1) {
        return { result: pureCircuits.arbiterCommitment(...args_1), context };
      },
      async milestoneKey(context, ...args_1) {
        return { result: pureCircuits.milestoneKey(...args_1), context };
      },
      createDeal: async (...args_1) => {
        if (args_1.length !== 8) {
          throw new __compactRuntime.CompactError(`createDeal: expected 8 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealRef_0 = args_1[1];
        const count_0 = args_1[2];
        const organizerCommitmentInput_0 = args_1[3];
        const arbiterCommitmentInput_0 = args_1[4];
        const arbiterDeadline_0 = args_1[5];
        const agentPk_0 = args_1[6];
        const organizerPk_0 = args_1[7];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('createDeal',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 113 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(dealRef_0.buffer instanceof ArrayBuffer && dealRef_0.BYTES_PER_ELEMENT === 1 && dealRef_0.length === 32)) {
          __compactRuntime.typeError('createDeal',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 113 char 1',
                                     'Bytes<32>',
                                     dealRef_0)
        }
        if (!(typeof(count_0) === 'bigint' && count_0 >= 0n && count_0 <= 255n)) {
          __compactRuntime.typeError('createDeal',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 113 char 1',
                                     'Uint<0..256>',
                                     count_0)
        }
        if (!(organizerCommitmentInput_0.buffer instanceof ArrayBuffer && organizerCommitmentInput_0.BYTES_PER_ELEMENT === 1 && organizerCommitmentInput_0.length === 32)) {
          __compactRuntime.typeError('createDeal',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 113 char 1',
                                     'Bytes<32>',
                                     organizerCommitmentInput_0)
        }
        if (!(arbiterCommitmentInput_0.buffer instanceof ArrayBuffer && arbiterCommitmentInput_0.BYTES_PER_ELEMENT === 1 && arbiterCommitmentInput_0.length === 32)) {
          __compactRuntime.typeError('createDeal',
                                     'argument 4 (argument 5 as invoked from Typescript)',
                                     'milestone.compact line 113 char 1',
                                     'Bytes<32>',
                                     arbiterCommitmentInput_0)
        }
        if (!(typeof(arbiterDeadline_0) === 'bigint' && arbiterDeadline_0 >= 0n && arbiterDeadline_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('createDeal',
                                     'argument 5 (argument 6 as invoked from Typescript)',
                                     'milestone.compact line 113 char 1',
                                     'Uint<0..18446744073709551616>',
                                     arbiterDeadline_0)
        }
        if (!(typeof(agentPk_0) === 'object' && agentPk_0.bytes.buffer instanceof ArrayBuffer && agentPk_0.bytes.BYTES_PER_ELEMENT === 1 && agentPk_0.bytes.length === 32)) {
          __compactRuntime.typeError('createDeal',
                                     'argument 6 (argument 7 as invoked from Typescript)',
                                     'milestone.compact line 113 char 1',
                                     'struct ZswapCoinPublicKey<bytes: Bytes<32>>',
                                     agentPk_0)
        }
        if (!(typeof(organizerPk_0) === 'object' && organizerPk_0.bytes.buffer instanceof ArrayBuffer && organizerPk_0.bytes.BYTES_PER_ELEMENT === 1 && organizerPk_0.bytes.length === 32)) {
          __compactRuntime.typeError('createDeal',
                                     'argument 7 (argument 8 as invoked from Typescript)',
                                     'milestone.compact line 113 char 1',
                                     'struct ZswapCoinPublicKey<bytes: Bytes<32>>',
                                     organizerPk_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_3.toValue(dealRef_0).concat(_descriptor_2.toValue(count_0).concat(_descriptor_3.toValue(organizerCommitmentInput_0).concat(_descriptor_3.toValue(arbiterCommitmentInput_0).concat(_descriptor_0.toValue(arbiterDeadline_0).concat(_descriptor_5.toValue(agentPk_0).concat(_descriptor_5.toValue(organizerPk_0))))))),
            alignment: _descriptor_3.alignment().concat(_descriptor_2.alignment().concat(_descriptor_3.alignment().concat(_descriptor_3.alignment().concat(_descriptor_0.alignment().concat(_descriptor_5.alignment().concat(_descriptor_5.alignment()))))))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._createDeal_0(context,
                                                  partialProofData,
                                                  dealRef_0,
                                                  count_0,
                                                  organizerCommitmentInput_0,
                                                  arbiterCommitmentInput_0,
                                                  arbiterDeadline_0,
                                                  agentPk_0,
                                                  organizerPk_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      createMilestone: async (...args_1) => {
        if (args_1.length !== 6) {
          throw new __compactRuntime.CompactError(`createMilestone: expected 6 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const amount_0 = args_1[2];
        const deadline_0 = args_1[3];
        const claimDeadline_0 = args_1[4];
        const deposit_0 = args_1[5];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('createMilestone',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 148 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('createMilestone',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 148 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(amount_0) === 'bigint' && amount_0 >= 0n && amount_0 <= 340282366920938463463374607431768211455n)) {
          __compactRuntime.typeError('createMilestone',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 148 char 1',
                                     'Uint<0..340282366920938463463374607431768211456>',
                                     amount_0)
        }
        if (!(typeof(deadline_0) === 'bigint' && deadline_0 >= 0n && deadline_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('createMilestone',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 148 char 1',
                                     'Uint<0..18446744073709551616>',
                                     deadline_0)
        }
        if (!(typeof(claimDeadline_0) === 'bigint' && claimDeadline_0 >= 0n && claimDeadline_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('createMilestone',
                                     'argument 4 (argument 5 as invoked from Typescript)',
                                     'milestone.compact line 148 char 1',
                                     'Uint<0..18446744073709551616>',
                                     claimDeadline_0)
        }
        if (!(typeof(deposit_0) === 'object' && deposit_0.nonce.buffer instanceof ArrayBuffer && deposit_0.nonce.BYTES_PER_ELEMENT === 1 && deposit_0.nonce.length === 32 && deposit_0.color.buffer instanceof ArrayBuffer && deposit_0.color.BYTES_PER_ELEMENT === 1 && deposit_0.color.length === 32 && typeof(deposit_0.value) === 'bigint' && deposit_0.value >= 0n && deposit_0.value <= 340282366920938463463374607431768211455n)) {
          __compactRuntime.typeError('createMilestone',
                                     'argument 5 (argument 6 as invoked from Typescript)',
                                     'milestone.compact line 148 char 1',
                                     'struct ShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>>',
                                     deposit_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_1.toValue(amount_0).concat(_descriptor_0.toValue(deadline_0).concat(_descriptor_0.toValue(claimDeadline_0).concat(_descriptor_9.toValue(deposit_0))))),
            alignment: _descriptor_0.alignment().concat(_descriptor_1.alignment().concat(_descriptor_0.alignment().concat(_descriptor_0.alignment().concat(_descriptor_9.alignment()))))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._createMilestone_0(context,
                                                       partialProofData,
                                                       dealId_0,
                                                       amount_0,
                                                       deadline_0,
                                                       claimDeadline_0,
                                                       deposit_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      releaseMilestone: async (...args_1) => {
        if (args_1.length !== 4) {
          throw new __compactRuntime.CompactError(`releaseMilestone: expected 4 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        const spendCoin_0 = args_1[3];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('releaseMilestone',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 213 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('releaseMilestone',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 213 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('releaseMilestone',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 213 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('releaseMilestone',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 213 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0).concat(_descriptor_7.toValue(spendCoin_0))),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment().concat(_descriptor_7.alignment()))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._releaseMilestone_0(context,
                                                        partialProofData,
                                                        dealId_0,
                                                        idx_0,
                                                        spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      refundMilestone: async (...args_1) => {
        if (args_1.length !== 4) {
          throw new __compactRuntime.CompactError(`refundMilestone: expected 4 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        const spendCoin_0 = args_1[3];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('refundMilestone',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 244 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('refundMilestone',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 244 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('refundMilestone',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 244 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('refundMilestone',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 244 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0).concat(_descriptor_7.toValue(spendCoin_0))),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment().concat(_descriptor_7.alignment()))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._refundMilestone_0(context,
                                                       partialProofData,
                                                       dealId_0,
                                                       idx_0,
                                                       spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      timeoutRefund: async (...args_1) => {
        if (args_1.length !== 4) {
          throw new __compactRuntime.CompactError(`timeoutRefund: expected 4 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        const spendCoin_0 = args_1[3];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('timeoutRefund',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 275 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('timeoutRefund',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 275 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('timeoutRefund',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 275 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('timeoutRefund',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 275 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0).concat(_descriptor_7.toValue(spendCoin_0))),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment().concat(_descriptor_7.alignment()))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._timeoutRefund_0(context,
                                                     partialProofData,
                                                     dealId_0,
                                                     idx_0,
                                                     spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      autoRelease: async (...args_1) => {
        if (args_1.length !== 4) {
          throw new __compactRuntime.CompactError(`autoRelease: expected 4 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        const spendCoin_0 = args_1[3];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('autoRelease',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 304 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('autoRelease',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 304 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('autoRelease',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 304 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('autoRelease',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 304 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0).concat(_descriptor_7.toValue(spendCoin_0))),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment().concat(_descriptor_7.alignment()))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._autoRelease_0(context,
                                                   partialProofData,
                                                   dealId_0,
                                                   idx_0,
                                                   spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      agentOpenDispute: async (...args_1) => {
        if (args_1.length !== 3) {
          throw new __compactRuntime.CompactError(`agentOpenDispute: expected 3 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('agentOpenDispute',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 330 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('agentOpenDispute',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 330 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('agentOpenDispute',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 330 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0)),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment())
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._agentOpenDispute_0(context,
                                                        partialProofData,
                                                        dealId_0,
                                                        idx_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      organizerOpenDispute: async (...args_1) => {
        if (args_1.length !== 3) {
          throw new __compactRuntime.CompactError(`organizerOpenDispute: expected 3 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('organizerOpenDispute',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 348 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('organizerOpenDispute',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 348 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('organizerOpenDispute',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 348 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0)),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment())
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._organizerOpenDispute_0(context,
                                                            partialProofData,
                                                            dealId_0,
                                                            idx_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      arbiterRelease: async (...args_1) => {
        if (args_1.length !== 4) {
          throw new __compactRuntime.CompactError(`arbiterRelease: expected 4 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        const spendCoin_0 = args_1[3];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('arbiterRelease',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 369 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('arbiterRelease',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 369 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('arbiterRelease',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 369 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('arbiterRelease',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 369 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0).concat(_descriptor_7.toValue(spendCoin_0))),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment().concat(_descriptor_7.alignment()))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._arbiterRelease_0(context,
                                                      partialProofData,
                                                      dealId_0,
                                                      idx_0,
                                                      spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      arbiterRefund: async (...args_1) => {
        if (args_1.length !== 4) {
          throw new __compactRuntime.CompactError(`arbiterRefund: expected 4 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        const spendCoin_0 = args_1[3];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('arbiterRefund',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 399 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('arbiterRefund',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 399 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('arbiterRefund',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 399 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('arbiterRefund',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 399 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0).concat(_descriptor_7.toValue(spendCoin_0))),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment().concat(_descriptor_7.alignment()))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._arbiterRefund_0(context,
                                                     partialProofData,
                                                     dealId_0,
                                                     idx_0,
                                                     spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      },
      arbiterTimeoutRefund: async (...args_1) => {
        if (args_1.length !== 4) {
          throw new __compactRuntime.CompactError(`arbiterTimeoutRefund: expected 4 arguments (as invoked from Typescript), received ${args_1.length}`);
        }
        const contextOrig_0 = args_1[0];
        const dealId_0 = args_1[1];
        const idx_0 = args_1[2];
        const spendCoin_0 = args_1[3];
        if (!(typeof(contextOrig_0) === 'object' && contextOrig_0.callContext.currentQueryContext != undefined)) {
          __compactRuntime.typeError('arbiterTimeoutRefund',
                                     'argument 1 (as invoked from Typescript)',
                                     'milestone.compact line 430 char 1',
                                     'CircuitContext',
                                     contextOrig_0)
        }
        if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
          __compactRuntime.typeError('arbiterTimeoutRefund',
                                     'argument 1 (argument 2 as invoked from Typescript)',
                                     'milestone.compact line 430 char 1',
                                     'Uint<0..18446744073709551616>',
                                     dealId_0)
        }
        if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
          __compactRuntime.typeError('arbiterTimeoutRefund',
                                     'argument 2 (argument 3 as invoked from Typescript)',
                                     'milestone.compact line 430 char 1',
                                     'Uint<0..256>',
                                     idx_0)
        }
        if (!(typeof(spendCoin_0) === 'object' && spendCoin_0.nonce.buffer instanceof ArrayBuffer && spendCoin_0.nonce.BYTES_PER_ELEMENT === 1 && spendCoin_0.nonce.length === 32 && spendCoin_0.color.buffer instanceof ArrayBuffer && spendCoin_0.color.BYTES_PER_ELEMENT === 1 && spendCoin_0.color.length === 32 && typeof(spendCoin_0.value) === 'bigint' && spendCoin_0.value >= 0n && spendCoin_0.value <= 340282366920938463463374607431768211455n && typeof(spendCoin_0.mt_index) === 'bigint' && spendCoin_0.mt_index >= 0n && spendCoin_0.mt_index <= 18446744073709551615n)) {
          __compactRuntime.typeError('arbiterTimeoutRefund',
                                     'argument 3 (argument 4 as invoked from Typescript)',
                                     'milestone.compact line 430 char 1',
                                     'struct QualifiedShieldedCoinInfo<nonce: Bytes<32>, color: Bytes<32>, value: Uint<0..340282366920938463463374607431768211456>, mt_index: Uint<0..18446744073709551616>>',
                                     spendCoin_0)
        }
        const context = __compactRuntime.copyCircuitContext(contextOrig_0);
        const partialProofData = {
          input: {
            value: _descriptor_0.toValue(dealId_0).concat(_descriptor_2.toValue(idx_0).concat(_descriptor_7.toValue(spendCoin_0))),
            alignment: _descriptor_0.alignment().concat(_descriptor_2.alignment().concat(_descriptor_7.alignment()))
          },
          output: undefined,
          publicTranscript: [],
          privateTranscriptOutputs: []
        };
        const result_0 = await this._arbiterTimeoutRefund_0(context,
                                                            partialProofData,
                                                            dealId_0,
                                                            idx_0,
                                                            spendCoin_0);
        partialProofData.output = { value: [], alignment: [] };
        __compactRuntime.finalizeCallProofData(context, partialProofData);
        return { result: result_0, context: context, gasCost: context.callContext.currentGasCost };
      }
    };
    this.impureCircuits = {
      createDeal: this.circuits.createDeal,
      createMilestone: this.circuits.createMilestone,
      releaseMilestone: this.circuits.releaseMilestone,
      refundMilestone: this.circuits.refundMilestone,
      timeoutRefund: this.circuits.timeoutRefund,
      autoRelease: this.circuits.autoRelease,
      agentOpenDispute: this.circuits.agentOpenDispute,
      organizerOpenDispute: this.circuits.organizerOpenDispute,
      arbiterRelease: this.circuits.arbiterRelease,
      arbiterRefund: this.circuits.arbiterRefund,
      arbiterTimeoutRefund: this.circuits.arbiterTimeoutRefund
    };
    this.provableCircuits = {
      createDeal: this.circuits.createDeal,
      createMilestone: this.circuits.createMilestone,
      releaseMilestone: this.circuits.releaseMilestone,
      refundMilestone: this.circuits.refundMilestone,
      timeoutRefund: this.circuits.timeoutRefund,
      autoRelease: this.circuits.autoRelease,
      agentOpenDispute: this.circuits.agentOpenDispute,
      organizerOpenDispute: this.circuits.organizerOpenDispute,
      arbiterRelease: this.circuits.arbiterRelease,
      arbiterRefund: this.circuits.arbiterRefund,
      arbiterTimeoutRefund: this.circuits.arbiterTimeoutRefund
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
    state_0.data = new __compactRuntime.ChargedState(stateValue_0);
    state_0.setOperation('createDeal', new __compactRuntime.ContractOperation());
    state_0.setOperation('createMilestone', new __compactRuntime.ContractOperation());
    state_0.setOperation('releaseMilestone', new __compactRuntime.ContractOperation());
    state_0.setOperation('refundMilestone', new __compactRuntime.ContractOperation());
    state_0.setOperation('timeoutRefund', new __compactRuntime.ContractOperation());
    state_0.setOperation('autoRelease', new __compactRuntime.ContractOperation());
    state_0.setOperation('agentOpenDispute', new __compactRuntime.ContractOperation());
    state_0.setOperation('organizerOpenDispute', new __compactRuntime.ContractOperation());
    state_0.setOperation('arbiterRelease', new __compactRuntime.ContractOperation());
    state_0.setOperation('arbiterRefund', new __compactRuntime.ContractOperation());
    state_0.setOperation('arbiterTimeoutRefund', new __compactRuntime.ContractOperation());
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
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(0n),
                                                                                              alignment: _descriptor_2.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newMap(
                                                          new __compactRuntime.StateMap()
                                                        ).encode() } },
                                       { ins: { cached: false, n: 1 } }]);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(1n),
                                                                                              alignment: _descriptor_2.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newMap(
                                                          new __compactRuntime.StateMap()
                                                        ).encode() } },
                                       { ins: { cached: false, n: 1 } }]);
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_2.toValue(2n),
                                                                                              alignment: _descriptor_2.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(0n),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
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
    const recipient_0 = this._right_0(_descriptor_11.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                                 partialProofData,
                                                                                                 [
                                                                                                  { dup: { n: 2 } },
                                                                                                  { idx: { cached: true,
                                                                                                           pushPath: false,
                                                                                                           path: [
                                                                                                                  { tag: 'value',
                                                                                                                    value: { value: _descriptor_2.toValue(0n),
                                                                                                                             alignment: _descriptor_2.alignment() } }] } },
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
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(tmp_0),
                                                                                              alignment: _descriptor_3.alignment() }).encode() } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newNull().encode() } },
                                       { ins: { cached: true, n: 2 } },
                                       { swap: { n: 0 } }]);
    return [];
  }
  async _sendShielded_0(context, partialProofData, input_0, recipient_0, value_0)
  {
    const selfAddr_0 = _descriptor_11.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                  partialProofData,
                                                                                  [
                                                                                   { dup: { n: 2 } },
                                                                                   { idx: { cached: true,
                                                                                            pushPath: false,
                                                                                            path: [
                                                                                                   { tag: 'value',
                                                                                                     value: { value: _descriptor_2.toValue(0n),
                                                                                                              alignment: _descriptor_2.alignment() } }] } },
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
                                                         value: { value: _descriptor_2.toValue(0n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(tmp_0),
                                                                                              alignment: _descriptor_3.alignment() }).encode() } },
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
                                                         value: { value: _descriptor_2.toValue(2n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(tmp_1),
                                                                                              alignment: _descriptor_3.alignment() }).encode() } },
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
                                                           value: { value: _descriptor_2.toValue(1n),
                                                                    alignment: _descriptor_2.alignment() } }] } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(tmp_2),
                                                                                                alignment: _descriptor_3.alignment() }).encode() } },
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
                                                           value: { value: _descriptor_2.toValue(2n),
                                                                    alignment: _descriptor_2.alignment() } }] } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(cm_0),
                                                                                                alignment: _descriptor_3.alignment() }).encode() } },
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
                                                           value: { value: _descriptor_2.toValue(1n),
                                                                    alignment: _descriptor_2.alignment() } }] } },
                                         { push: { storage: false,
                                                   value: __compactRuntime.StateValue.newCell({ value: _descriptor_3.toValue(cm_0),
                                                                                                alignment: _descriptor_3.alignment() }).encode() } },
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
    return _descriptor_8.fromValue(__compactRuntime.queryLedgerState(context,
                                                                     partialProofData,
                                                                     [
                                                                      { dup: { n: 2 } },
                                                                      { idx: { cached: true,
                                                                               pushPath: false,
                                                                               path: [
                                                                                      { tag: 'value',
                                                                                        value: { value: _descriptor_2.toValue(2n),
                                                                                                 alignment: _descriptor_2.alignment() } }] } },
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
    const result_0 = __compactRuntime.transientHash(_descriptor_17, value_0);
    return result_0;
  }
  _persistentHash_0(value_0) {
    const result_0 = __compactRuntime.persistentHash(_descriptor_14, value_0);
    return result_0;
  }
  _persistentHash_1(value_0) {
    const result_0 = __compactRuntime.persistentHash(_descriptor_16, value_0);
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
                                 'milestone.compact line 80 char 1',
                                 'Bytes<32>',
                                 result_0)
    }
    partialProofData.privateTranscriptOutputs.push({
      value: _descriptor_3.toValue(result_0),
      alignment: _descriptor_3.alignment()
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
                                 'milestone.compact line 81 char 1',
                                 'Bytes<32>',
                                 result_0)
    }
    partialProofData.privateTranscriptOutputs.push({
      value: _descriptor_3.toValue(result_0),
      alignment: _descriptor_3.alignment()
    });
    return result_0;
  }
  _arbiterSecretKey_0(context, partialProofData) {
    const witnessContext_0 = __compactRuntime.createWitnessContext(ledger(context.callContext.currentQueryContext.state), context.callContext.currentPrivateState, context.callContext.currentQueryContext.address);
    const [nextPrivateState_0, result_0] = this.witnesses.arbiterSecretKey(witnessContext_0);
    context.callContext.currentPrivateState = nextPrivateState_0;
    if (!(result_0.buffer instanceof ArrayBuffer && result_0.BYTES_PER_ELEMENT === 1 && result_0.length === 32)) {
      __compactRuntime.typeError('arbiterSecretKey',
                                 'return value',
                                 'milestone.compact line 82 char 1',
                                 'Bytes<32>',
                                 result_0)
    }
    partialProofData.privateTranscriptOutputs.push({
      value: _descriptor_3.toValue(result_0),
      alignment: _descriptor_3.alignment()
    });
    return result_0;
  }
  _agentCommitment_0(sk_0, dealRef_0) {
    return this._persistentHash_0([new Uint8Array([101, 118, 101, 114, 108, 105, 115, 116, 58, 109, 105, 108, 101, 115, 116, 111, 110, 101, 58, 97, 103, 101, 110, 116, 58, 0, 0, 0, 0, 0, 0, 0]),
                                   sk_0,
                                   dealRef_0]);
  }
  _organizerCommitment_0(sk_0, dealRef_0) {
    return this._persistentHash_0([new Uint8Array([101, 118, 101, 114, 108, 105, 115, 116, 58, 109, 105, 108, 101, 115, 116, 111, 110, 101, 58, 111, 114, 103, 97, 110, 105, 122, 101, 114, 58, 0, 0, 0]),
                                   sk_0,
                                   dealRef_0]);
  }
  _arbiterCommitment_0(sk_0, dealRef_0) {
    return this._persistentHash_0([new Uint8Array([101, 118, 101, 114, 108, 105, 115, 116, 58, 109, 105, 108, 101, 115, 116, 111, 110, 101, 58, 97, 114, 98, 105, 116, 101, 114, 58, 0, 0, 0, 0, 0]),
                                   sk_0,
                                   dealRef_0]);
  }
  _milestoneKey_0(dealId_0, idx_0) {
    return ((t1) => {
             if (t1 > 18446744073709551615n) {
               throw new __compactRuntime.CompactError('milestone.compact line 105 char 10: cast from Field or Uint value to smaller Uint value failed: ' + t1 + ' is greater than 18446744073709551615');
             }
             return t1;
           })(dealId_0 * 100n + idx_0);
  }
  async _createDeal_0(context,
                      partialProofData,
                      dealRef_0,
                      count_0,
                      organizerCommitmentInput_0,
                      arbiterCommitmentInput_0,
                      arbiterDeadline_0,
                      agentPk_0,
                      organizerPk_0)
  {
    __compactRuntime.assert(count_0 >= 1n, 'deal needs at least one milestone');
    __compactRuntime.assert(count_0 <= 12n, 'deal allows at most 12 milestones');
    const tmp_0 = 1n;
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(2n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { addi: { immediate: parseInt(__compactRuntime.valueToBigInt(
                                                              { value: _descriptor_10.toValue(tmp_0),
                                                                alignment: _descriptor_10.alignment() }
                                                                .value
                                                            )) } },
                                       { ins: { cached: true, n: 1 } }]);
    const did_0 = _descriptor_0.fromValue(__compactRuntime.queryLedgerState(context,
                                                                            partialProofData,
                                                                            [
                                                                             { dup: { n: 0 } },
                                                                             { idx: { cached: false,
                                                                                      pushPath: false,
                                                                                      path: [
                                                                                             { tag: 'value',
                                                                                               value: { value: _descriptor_2.toValue(2n),
                                                                                                        alignment: _descriptor_2.alignment() } }] } },
                                                                             { popeq: { cached: true,
                                                                                        result: undefined } }]).value);
    const aComm_0 = this._agentCommitment_0(this._agentSecretKey_0(context,
                                                                   partialProofData),
                                            dealRef_0);
    const tmp_1 = { dealRef: dealRef_0,
                    agentCommitment: aComm_0,
                    organizerCommitment: organizerCommitmentInput_0,
                    arbiterCommitment: arbiterCommitmentInput_0,
                    count: count_0,
                    created: 0n,
                    arbiterDeadline: arbiterDeadline_0,
                    agentPk: agentPk_0,
                    organizerPk: organizerPk_0 };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(0n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(did_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_6.toValue(tmp_1),
                                                                                              alignment: _descriptor_6.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _createMilestone_0(context,
                           partialProofData,
                           dealId_0,
                           amount_0,
                           deadline_0,
                           claimDeadline_0,
                           deposit_0)
  {
    const did_0 = dealId_0;
    __compactRuntime.assert(_descriptor_8.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                      partialProofData,
                                                                                      [
                                                                                       { dup: { n: 0 } },
                                                                                       { idx: { cached: false,
                                                                                                pushPath: false,
                                                                                                path: [
                                                                                                       { tag: 'value',
                                                                                                         value: { value: _descriptor_2.toValue(0n),
                                                                                                                  alignment: _descriptor_2.alignment() } }] } },
                                                                                       { push: { storage: false,
                                                                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(did_0),
                                                                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                                                                       'member',
                                                                                       { popeq: { cached: true,
                                                                                                  result: undefined } }]).value),
                            'deal not found');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(did_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    const caller_0 = this._agentCommitment_0(this._agentSecretKey_0(context,
                                                                    partialProofData),
                                             d_0.dealRef);
    __compactRuntime.assert(this._equal_1(caller_0, d_0.agentCommitment),
                            'only agent can fund milestones');
    __compactRuntime.assert(amount_0 > 0n, 'amount must be positive');
    __compactRuntime.assert(deposit_0.value === amount_0,
                            'deposit must equal milestone amount');
    __compactRuntime.assert(claimDeadline_0 > deadline_0,
                            'claim deadline must be after refund deadline');
    const idx_0 = d_0.created;
    __compactRuntime.assert(idx_0 < d_0.count, 'all milestones already funded');
    if (idx_0 > 0n) {
      let tmp_0;
      const prev_0 = (tmp_0 = this._milestoneKey_0(dealId_0,
                                                   (__compactRuntime.assert(idx_0
                                                                            >=
                                                                            1n,
                                                                            'result of subtraction would be negative'),
                                                    idx_0 - 1n)),
                      _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                partialProofData,
                                                                                [
                                                                                 { dup: { n: 0 } },
                                                                                 { idx: { cached: false,
                                                                                          pushPath: false,
                                                                                          path: [
                                                                                                 { tag: 'value',
                                                                                                   value: { value: _descriptor_2.toValue(1n),
                                                                                                            alignment: _descriptor_2.alignment() } }] } },
                                                                                 { idx: { cached: false,
                                                                                          pushPath: false,
                                                                                          path: [
                                                                                                 { tag: 'value',
                                                                                                   value: { value: _descriptor_0.toValue(tmp_0),
                                                                                                            alignment: _descriptor_0.alignment() } }] } },
                                                                                 { popeq: { cached: false,
                                                                                            result: undefined } }]).value));
      let t_0;
      __compactRuntime.assert((t_0 = prev_0.state, t_0 >= 3n),
                              'previous milestone not settled (held or disputed)');
    }
    await this._receiveShielded_0(context, partialProofData, deposit_0);
    const tmp_1 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_2 = { amount: amount_0,
                    state: 1n,
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
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_1),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_2),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    const tmp_3 = { dealRef: d_0.dealRef,
                    agentCommitment: d_0.agentCommitment,
                    organizerCommitment: d_0.organizerCommitment,
                    arbiterCommitment: d_0.arbiterCommitment,
                    count: d_0.count,
                    created:
                      ((t1) => {
                        if (t1 > 255n) {
                          throw new __compactRuntime.CompactError('milestone.compact line 190 char 23: cast from Field or Uint value to smaller Uint value failed: ' + t1 + ' is greater than 255');
                        }
                        return t1;
                      })(d_0.created + 1n),
                    arbiterDeadline: d_0.arbiterDeadline,
                    agentPk: d_0.agentPk,
                    organizerPk: d_0.organizerPk };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(0n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(did_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_6.toValue(tmp_3),
                                                                                              alignment: _descriptor_6.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _current_0(context, partialProofData, dealId_0, idx_0) {
    const did_0 = dealId_0;
    __compactRuntime.assert(_descriptor_8.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                      partialProofData,
                                                                                      [
                                                                                       { dup: { n: 0 } },
                                                                                       { idx: { cached: false,
                                                                                                pushPath: false,
                                                                                                path: [
                                                                                                       { tag: 'value',
                                                                                                         value: { value: _descriptor_2.toValue(0n),
                                                                                                                  alignment: _descriptor_2.alignment() } }] } },
                                                                                       { push: { storage: false,
                                                                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(did_0),
                                                                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                                                                       'member',
                                                                                       { popeq: { cached: true,
                                                                                                  result: undefined } }]).value),
                            'deal not found');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(did_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(idx_0 < d_0.created, 'milestone not funded yet');
    let tmp_0;
    __compactRuntime.assert((tmp_0 = this._milestoneKey_0(dealId_0, idx_0),
                             _descriptor_8.fromValue(__compactRuntime.queryLedgerState(context,
                                                                                       partialProofData,
                                                                                       [
                                                                                        { dup: { n: 0 } },
                                                                                        { idx: { cached: false,
                                                                                                 pushPath: false,
                                                                                                 path: [
                                                                                                        { tag: 'value',
                                                                                                          value: { value: _descriptor_2.toValue(1n),
                                                                                                                   alignment: _descriptor_2.alignment() } }] } },
                                                                                        { push: { storage: false,
                                                                                                  value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                                                                               alignment: _descriptor_0.alignment() }).encode() } },
                                                                                        'member',
                                                                                        { popeq: { cached: true,
                                                                                                   result: undefined } }]).value)),
                            'milestone not found');
    const tmp_1 = this._milestoneKey_0(dealId_0, idx_0);
    return _descriptor_4.fromValue(__compactRuntime.queryLedgerState(context,
                                                                     partialProofData,
                                                                     [
                                                                      { dup: { n: 0 } },
                                                                      { idx: { cached: false,
                                                                               pushPath: false,
                                                                               path: [
                                                                                      { tag: 'value',
                                                                                        value: { value: _descriptor_2.toValue(1n),
                                                                                                 alignment: _descriptor_2.alignment() } }] } },
                                                                      { idx: { cached: false,
                                                                               pushPath: false,
                                                                               path: [
                                                                                      { tag: 'value',
                                                                                        value: { value: _descriptor_0.toValue(tmp_1),
                                                                                                 alignment: _descriptor_0.alignment() } }] } },
                                                                      { popeq: { cached: false,
                                                                                 result: undefined } }]).value);
  }
  async _releaseMilestone_0(context,
                            partialProofData,
                            dealId_0,
                            idx_0,
                            spendCoin_0)
  {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 1n, 'milestone not in HELD state');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    const caller_0 = this._organizerCommitment_0(this._organizerSecretKey_0(context,
                                                                            partialProofData),
                                                 d_0.dealRef);
    __compactRuntime.assert(this._equal_2(caller_0, d_0.organizerCommitment),
                            'only organizer can release');
    __compactRuntime.assert(this._equal_3(spendCoin_0.nonce, m_0.coinNonce),
                            'coin does not match custody');
    __compactRuntime.assert(this._equal_4(spendCoin_0.color, m_0.coinColor),
                            'coin does not match custody');
    __compactRuntime.assert(spendCoin_0.value === m_0.amount,
                            'coin does not match custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(d_0.organizerPk),
                               m_0.amount);
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 3n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _refundMilestone_0(context,
                           partialProofData,
                           dealId_0,
                           idx_0,
                           spendCoin_0)
  {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 1n, 'milestone not in HELD state');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    const caller_0 = this._agentCommitment_0(this._agentSecretKey_0(context,
                                                                    partialProofData),
                                             d_0.dealRef);
    __compactRuntime.assert(this._equal_5(caller_0, d_0.agentCommitment),
                            'only agent can refund');
    __compactRuntime.assert(!await this._blockTimeGte_0(context,
                                                        partialProofData,
                                                        m_0.claimDeadline),
                            'claim deadline passed - organizer auto-release applies');
    __compactRuntime.assert(this._equal_6(spendCoin_0.nonce, m_0.coinNonce),
                            'coin does not match custody');
    __compactRuntime.assert(this._equal_7(spendCoin_0.color, m_0.coinColor),
                            'coin does not match custody');
    __compactRuntime.assert(spendCoin_0.value === m_0.amount,
                            'coin does not match custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(d_0.agentPk),
                               m_0.amount);
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 4n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _timeoutRefund_0(context, partialProofData, dealId_0, idx_0, spendCoin_0)
  {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 1n, 'milestone not in HELD state');
    __compactRuntime.assert(await this._blockTimeGte_0(context,
                                                       partialProofData,
                                                       m_0.deadline),
                            'refund deadline not yet passed');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(this._equal_8(spendCoin_0.nonce, m_0.coinNonce),
                            'coin does not match custody');
    __compactRuntime.assert(this._equal_9(spendCoin_0.color, m_0.coinColor),
                            'coin does not match custody');
    __compactRuntime.assert(spendCoin_0.value === m_0.amount,
                            'coin does not match custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(d_0.agentPk),
                               m_0.amount);
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 4n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _autoRelease_0(context, partialProofData, dealId_0, idx_0, spendCoin_0)
  {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 1n, 'milestone not in HELD state');
    __compactRuntime.assert(await this._blockTimeGte_0(context,
                                                       partialProofData,
                                                       m_0.claimDeadline),
                            'claim deadline not yet passed');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(this._equal_10(spendCoin_0.nonce, m_0.coinNonce),
                            'coin does not match custody');
    __compactRuntime.assert(this._equal_11(spendCoin_0.color, m_0.coinColor),
                            'coin does not match custody');
    __compactRuntime.assert(spendCoin_0.value === m_0.amount,
                            'coin does not match custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(d_0.organizerPk),
                               m_0.amount);
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 3n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _agentOpenDispute_0(context, partialProofData, dealId_0, idx_0) {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 1n, 'milestone not in HELD state');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    const caller_0 = this._agentCommitment_0(this._agentSecretKey_0(context,
                                                                    partialProofData),
                                             d_0.dealRef);
    __compactRuntime.assert(this._equal_12(caller_0, d_0.agentCommitment),
                            'only agent can open this dispute');
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 2n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _organizerOpenDispute_0(context, partialProofData, dealId_0, idx_0) {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 1n, 'milestone not in HELD state');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    const caller_0 = this._organizerCommitment_0(this._organizerSecretKey_0(context,
                                                                            partialProofData),
                                                 d_0.dealRef);
    __compactRuntime.assert(this._equal_13(caller_0, d_0.organizerCommitment),
                            'only organizer can open this dispute');
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 2n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _arbiterRelease_0(context,
                          partialProofData,
                          dealId_0,
                          idx_0,
                          spendCoin_0)
  {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 2n, 'milestone not in DISPUTED state');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    const caller_0 = this._arbiterCommitment_0(this._arbiterSecretKey_0(context,
                                                                        partialProofData),
                                               d_0.dealRef);
    __compactRuntime.assert(this._equal_14(caller_0, d_0.arbiterCommitment),
                            'only arbiter can rule');
    __compactRuntime.assert(this._equal_15(spendCoin_0.nonce, m_0.coinNonce),
                            'coin does not match custody');
    __compactRuntime.assert(this._equal_16(spendCoin_0.color, m_0.coinColor),
                            'coin does not match custody');
    __compactRuntime.assert(spendCoin_0.value === m_0.amount,
                            'coin does not match custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(d_0.organizerPk),
                               m_0.amount);
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 5n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _arbiterRefund_0(context, partialProofData, dealId_0, idx_0, spendCoin_0)
  {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 2n, 'milestone not in DISPUTED state');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    const caller_0 = this._arbiterCommitment_0(this._arbiterSecretKey_0(context,
                                                                        partialProofData),
                                               d_0.dealRef);
    __compactRuntime.assert(this._equal_17(caller_0, d_0.arbiterCommitment),
                            'only arbiter can rule');
    __compactRuntime.assert(this._equal_18(spendCoin_0.nonce, m_0.coinNonce),
                            'coin does not match custody');
    __compactRuntime.assert(this._equal_19(spendCoin_0.color, m_0.coinColor),
                            'coin does not match custody');
    __compactRuntime.assert(spendCoin_0.value === m_0.amount,
                            'coin does not match custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(d_0.agentPk),
                               m_0.amount);
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 6n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
  }
  async _arbiterTimeoutRefund_0(context,
                                partialProofData,
                                dealId_0,
                                idx_0,
                                spendCoin_0)
  {
    const m_0 = await this._current_0(context, partialProofData, dealId_0, idx_0);
    __compactRuntime.assert(m_0.state === 2n, 'milestone not in DISPUTED state');
    const d_0 = _descriptor_6.fromValue(__compactRuntime.queryLedgerState(context,
                                                                          partialProofData,
                                                                          [
                                                                           { dup: { n: 0 } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_2.toValue(0n),
                                                                                                      alignment: _descriptor_2.alignment() } }] } },
                                                                           { idx: { cached: false,
                                                                                    pushPath: false,
                                                                                    path: [
                                                                                           { tag: 'value',
                                                                                             value: { value: _descriptor_0.toValue(dealId_0),
                                                                                                      alignment: _descriptor_0.alignment() } }] } },
                                                                           { popeq: { cached: false,
                                                                                      result: undefined } }]).value);
    __compactRuntime.assert(await this._blockTimeGte_0(context,
                                                       partialProofData,
                                                       d_0.arbiterDeadline),
                            'arbiter deadline not yet passed');
    __compactRuntime.assert(this._equal_20(spendCoin_0.nonce, m_0.coinNonce),
                            'coin does not match custody');
    __compactRuntime.assert(this._equal_21(spendCoin_0.color, m_0.coinColor),
                            'coin does not match custody');
    __compactRuntime.assert(spendCoin_0.value === m_0.amount,
                            'coin does not match custody');
    await this._sendShielded_0(context,
                               partialProofData,
                               spendCoin_0,
                               this._left_0(d_0.agentPk),
                               m_0.amount);
    const tmp_0 = this._milestoneKey_0(dealId_0, idx_0);
    const tmp_1 = { amount: m_0.amount,
                    state: 6n,
                    deadline: m_0.deadline,
                    claimDeadline: m_0.claimDeadline,
                    coinNonce: m_0.coinNonce,
                    coinColor: m_0.coinColor };
    __compactRuntime.queryLedgerState(context,
                                      partialProofData,
                                      [
                                       { idx: { cached: false,
                                                pushPath: true,
                                                path: [
                                                       { tag: 'value',
                                                         value: { value: _descriptor_2.toValue(1n),
                                                                  alignment: _descriptor_2.alignment() } }] } },
                                       { push: { storage: false,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_0.toValue(tmp_0),
                                                                                              alignment: _descriptor_0.alignment() }).encode() } },
                                       { push: { storage: true,
                                                 value: __compactRuntime.StateValue.newCell({ value: _descriptor_4.toValue(tmp_1),
                                                                                              alignment: _descriptor_4.alignment() }).encode() } },
                                       { ins: { cached: false, n: 1 } },
                                       { ins: { cached: true, n: 1 } }]);
    return [];
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
  _equal_14(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_15(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_16(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_17(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_18(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_19(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_20(x0, y0) {
    if (!x0.every((x, i) => y0[i] === x)) { return false; }
    return true;
  }
  _equal_21(x0, y0) {
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
    deals: {
      isEmpty(...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`isEmpty: expected 0 arguments, received ${args_0.length}`);
        }
        return _descriptor_8.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_2.toValue(0n),
                                                                                                     alignment: _descriptor_2.alignment() } }] } },
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
                                                                                            value: { value: _descriptor_2.toValue(0n),
                                                                                                     alignment: _descriptor_2.alignment() } }] } },
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
                                     'milestone.compact line 76 char 1',
                                     'Uint<0..18446744073709551616>',
                                     key_0)
        }
        return _descriptor_8.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_2.toValue(0n),
                                                                                                     alignment: _descriptor_2.alignment() } }] } },
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
                                     'milestone.compact line 76 char 1',
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
                                                                                            value: { value: _descriptor_2.toValue(0n),
                                                                                                     alignment: _descriptor_2.alignment() } }] } },
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
        return self_0.asMap().keys().map(  (key) => {    const value = self_0.asMap().get(key).asCell();    return [      _descriptor_0.fromValue(key.value),      _descriptor_6.fromValue(value.value)    ];  })[Symbol.iterator]();
      }
    },
    milestones: {
      isEmpty(...args_0) {
        if (args_0.length !== 0) {
          throw new __compactRuntime.CompactError(`isEmpty: expected 0 arguments, received ${args_0.length}`);
        }
        return _descriptor_8.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_2.toValue(1n),
                                                                                                     alignment: _descriptor_2.alignment() } }] } },
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
                                                                                            value: { value: _descriptor_2.toValue(1n),
                                                                                                     alignment: _descriptor_2.alignment() } }] } },
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
                                     'milestone.compact line 77 char 1',
                                     'Uint<0..18446744073709551616>',
                                     key_0)
        }
        return _descriptor_8.fromValue(__compactRuntime.queryLedgerState(context,
                                                                         partialProofData,
                                                                         [
                                                                          { dup: { n: 0 } },
                                                                          { idx: { cached: false,
                                                                                   pushPath: false,
                                                                                   path: [
                                                                                          { tag: 'value',
                                                                                            value: { value: _descriptor_2.toValue(1n),
                                                                                                     alignment: _descriptor_2.alignment() } }] } },
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
                                     'milestone.compact line 77 char 1',
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
                                                                                            value: { value: _descriptor_2.toValue(1n),
                                                                                                     alignment: _descriptor_2.alignment() } }] } },
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
        const self_0 = state.asArray()[1];
        return self_0.asMap().keys().map(  (key) => {    const value = self_0.asMap().get(key).asCell();    return [      _descriptor_0.fromValue(key.value),      _descriptor_4.fromValue(value.value)    ];  })[Symbol.iterator]();
      }
    },
    get nextDealId() {
      return _descriptor_0.fromValue(__compactRuntime.queryLedgerState(context,
                                                                       partialProofData,
                                                                       [
                                                                        { dup: { n: 0 } },
                                                                        { idx: { cached: false,
                                                                                 pushPath: false,
                                                                                 path: [
                                                                                        { tag: 'value',
                                                                                          value: { value: _descriptor_2.toValue(2n),
                                                                                                   alignment: _descriptor_2.alignment() } }] } },
                                                                        { popeq: { cached: true,
                                                                                   result: undefined } }]).value);
    }
  };
}
const _emptyContext = {
  callContext: { currentQueryContext: new __compactRuntime.QueryContext(new __compactRuntime.ContractState().data, __compactRuntime.dummyContractAddress()), currentGasCost: __compactRuntime.emptyRunningCost() }
};
const _dummyContract = new Contract({
  agentSecretKey: (...args) => undefined,
  organizerSecretKey: (...args) => undefined,
  arbiterSecretKey: (...args) => undefined
});
export const pureCircuits = {
  agentCommitment: (...args_0) => {
    if (args_0.length !== 2) {
      throw new __compactRuntime.CompactError(`agentCommitment: expected 2 arguments (as invoked from Typescript), received ${args_0.length}`);
    }
    const sk_0 = args_0[0];
    const dealRef_0 = args_0[1];
    if (!(sk_0.buffer instanceof ArrayBuffer && sk_0.BYTES_PER_ELEMENT === 1 && sk_0.length === 32)) {
      __compactRuntime.typeError('agentCommitment',
                                 'argument 1',
                                 'milestone.compact line 85 char 1',
                                 'Bytes<32>',
                                 sk_0)
    }
    if (!(dealRef_0.buffer instanceof ArrayBuffer && dealRef_0.BYTES_PER_ELEMENT === 1 && dealRef_0.length === 32)) {
      __compactRuntime.typeError('agentCommitment',
                                 'argument 2',
                                 'milestone.compact line 85 char 1',
                                 'Bytes<32>',
                                 dealRef_0)
    }
    return _dummyContract._agentCommitment_0(sk_0, dealRef_0);
  },
  organizerCommitment: (...args_0) => {
    if (args_0.length !== 2) {
      throw new __compactRuntime.CompactError(`organizerCommitment: expected 2 arguments (as invoked from Typescript), received ${args_0.length}`);
    }
    const sk_0 = args_0[0];
    const dealRef_0 = args_0[1];
    if (!(sk_0.buffer instanceof ArrayBuffer && sk_0.BYTES_PER_ELEMENT === 1 && sk_0.length === 32)) {
      __compactRuntime.typeError('organizerCommitment',
                                 'argument 1',
                                 'milestone.compact line 90 char 1',
                                 'Bytes<32>',
                                 sk_0)
    }
    if (!(dealRef_0.buffer instanceof ArrayBuffer && dealRef_0.BYTES_PER_ELEMENT === 1 && dealRef_0.length === 32)) {
      __compactRuntime.typeError('organizerCommitment',
                                 'argument 2',
                                 'milestone.compact line 90 char 1',
                                 'Bytes<32>',
                                 dealRef_0)
    }
    return _dummyContract._organizerCommitment_0(sk_0, dealRef_0);
  },
  arbiterCommitment: (...args_0) => {
    if (args_0.length !== 2) {
      throw new __compactRuntime.CompactError(`arbiterCommitment: expected 2 arguments (as invoked from Typescript), received ${args_0.length}`);
    }
    const sk_0 = args_0[0];
    const dealRef_0 = args_0[1];
    if (!(sk_0.buffer instanceof ArrayBuffer && sk_0.BYTES_PER_ELEMENT === 1 && sk_0.length === 32)) {
      __compactRuntime.typeError('arbiterCommitment',
                                 'argument 1',
                                 'milestone.compact line 95 char 1',
                                 'Bytes<32>',
                                 sk_0)
    }
    if (!(dealRef_0.buffer instanceof ArrayBuffer && dealRef_0.BYTES_PER_ELEMENT === 1 && dealRef_0.length === 32)) {
      __compactRuntime.typeError('arbiterCommitment',
                                 'argument 2',
                                 'milestone.compact line 95 char 1',
                                 'Bytes<32>',
                                 dealRef_0)
    }
    return _dummyContract._arbiterCommitment_0(sk_0, dealRef_0);
  },
  milestoneKey: (...args_0) => {
    if (args_0.length !== 2) {
      throw new __compactRuntime.CompactError(`milestoneKey: expected 2 arguments (as invoked from Typescript), received ${args_0.length}`);
    }
    const dealId_0 = args_0[0];
    const idx_0 = args_0[1];
    if (!(typeof(dealId_0) === 'bigint' && dealId_0 >= 0n && dealId_0 <= 18446744073709551615n)) {
      __compactRuntime.typeError('milestoneKey',
                                 'argument 1',
                                 'milestone.compact line 100 char 1',
                                 'Uint<0..18446744073709551616>',
                                 dealId_0)
    }
    if (!(typeof(idx_0) === 'bigint' && idx_0 >= 0n && idx_0 <= 255n)) {
      __compactRuntime.typeError('milestoneKey',
                                 'argument 2',
                                 'milestone.compact line 100 char 1',
                                 'Uint<0..256>',
                                 idx_0)
    }
    return _dummyContract._milestoneKey_0(dealId_0, idx_0);
  }
};
export const contractReferenceLocations =
  { tag: 'publicLedgerArray', indices: { } };
export const expectedVk = {
  'agentOpenDispute': '71d94f89b266a60355a7b9867e4c59d464394a03efd3bb9abc32711e15fd4891',
  'arbiterRefund': 'b0e41eac33e47bd49845dbeaff017b4a858dcc7ff7fcde7fb865a1ee58889a0d',
  'arbiterRelease': '08aba0edec52ece680003cc22993eb8fd9e0f959c33f6b8f6d81ffa90249d94c',
  'arbiterTimeoutRefund': 'bc6649406e02cf9a20d97a41e83937fb4c82b61161c231e4623d32e450ddd1c7',
  'autoRelease': '06609230f785e750432111a08313ea29d9acfcd9c345bdb7a6dc7de42a9484f0',
  'createDeal': 'c0d1fd70bf68e264d2558a449483d4a887ed212aa8d9bd2cab644cc8f2ad4933',
  'createMilestone': 'cd6504ca9476a22e5aad8ab4147cfd55e08de2375e4f918275b986b72d77f8d4',
  'organizerOpenDispute': 'b457c7862f66d5e92070f84ce81f38c5556eea9bd85a6570e39e467de8e5d683',
  'refundMilestone': 'a323109c9f19aa430b23f4c548200e6cc04065e98abb8e3bee2023ab4847cd28',
  'releaseMilestone': '1ec03ee4dfb7d8375eaab425ef28d6d5f596ad52c2a314f838f81344b80339b7',
  'timeoutRefund': '69071543a14e26c3eb6d19d06352260db46c3517ace07f5f6fb42788b6ba49d1',
};

//# sourceMappingURL=index.js.map
