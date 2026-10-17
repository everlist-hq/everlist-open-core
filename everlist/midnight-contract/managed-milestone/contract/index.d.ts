import type * as __compactRuntime from '@midnight-ntwrk/compact-runtime';

export type Witnesses<PS> = {
  agentSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
  organizerSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
  arbiterSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
}

export type ImpureCircuits<PS> = {
  createDeal(context: __compactRuntime.CircuitContext<PS>,
             dealRef_0: Uint8Array,
             count_0: bigint,
             organizerCommitmentInput_0: Uint8Array,
             arbiterCommitmentInput_0: Uint8Array,
             arbiterDeadline_0: bigint,
             agentPk_0: { bytes: Uint8Array },
             organizerPk_0: { bytes: Uint8Array }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  createMilestone(context: __compactRuntime.CircuitContext<PS>,
                  dealId_0: bigint,
                  amount_0: bigint,
                  deadline_0: bigint,
                  claimDeadline_0: bigint,
                  deposit_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  releaseMilestone(context: __compactRuntime.CircuitContext<PS>,
                   dealId_0: bigint,
                   idx_0: bigint,
                   spendCoin_0: { nonce: Uint8Array,
                                  color: Uint8Array,
                                  value: bigint,
                                  mt_index: bigint
                                }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  refundMilestone(context: __compactRuntime.CircuitContext<PS>,
                  dealId_0: bigint,
                  idx_0: bigint,
                  spendCoin_0: { nonce: Uint8Array,
                                 color: Uint8Array,
                                 value: bigint,
                                 mt_index: bigint
                               }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  timeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                dealId_0: bigint,
                idx_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  autoRelease(context: __compactRuntime.CircuitContext<PS>,
              dealId_0: bigint,
              idx_0: bigint,
              spendCoin_0: { nonce: Uint8Array,
                             color: Uint8Array,
                             value: bigint,
                             mt_index: bigint
                           }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  agentOpenDispute(context: __compactRuntime.CircuitContext<PS>,
                   dealId_0: bigint,
                   idx_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  organizerOpenDispute(context: __compactRuntime.CircuitContext<PS>,
                       dealId_0: bigint,
                       idx_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterRelease(context: __compactRuntime.CircuitContext<PS>,
                 dealId_0: bigint,
                 idx_0: bigint,
                 spendCoin_0: { nonce: Uint8Array,
                                color: Uint8Array,
                                value: bigint,
                                mt_index: bigint
                              }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterRefund(context: __compactRuntime.CircuitContext<PS>,
                dealId_0: bigint,
                idx_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterTimeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                       dealId_0: bigint,
                       idx_0: bigint,
                       spendCoin_0: { nonce: Uint8Array,
                                      color: Uint8Array,
                                      value: bigint,
                                      mt_index: bigint
                                    }): Promise<__compactRuntime.CircuitResults<PS, []>>;
}

export type ProvableCircuits<PS> = {
  createDeal(context: __compactRuntime.CircuitContext<PS>,
             dealRef_0: Uint8Array,
             count_0: bigint,
             organizerCommitmentInput_0: Uint8Array,
             arbiterCommitmentInput_0: Uint8Array,
             arbiterDeadline_0: bigint,
             agentPk_0: { bytes: Uint8Array },
             organizerPk_0: { bytes: Uint8Array }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  createMilestone(context: __compactRuntime.CircuitContext<PS>,
                  dealId_0: bigint,
                  amount_0: bigint,
                  deadline_0: bigint,
                  claimDeadline_0: bigint,
                  deposit_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  releaseMilestone(context: __compactRuntime.CircuitContext<PS>,
                   dealId_0: bigint,
                   idx_0: bigint,
                   spendCoin_0: { nonce: Uint8Array,
                                  color: Uint8Array,
                                  value: bigint,
                                  mt_index: bigint
                                }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  refundMilestone(context: __compactRuntime.CircuitContext<PS>,
                  dealId_0: bigint,
                  idx_0: bigint,
                  spendCoin_0: { nonce: Uint8Array,
                                 color: Uint8Array,
                                 value: bigint,
                                 mt_index: bigint
                               }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  timeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                dealId_0: bigint,
                idx_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  autoRelease(context: __compactRuntime.CircuitContext<PS>,
              dealId_0: bigint,
              idx_0: bigint,
              spendCoin_0: { nonce: Uint8Array,
                             color: Uint8Array,
                             value: bigint,
                             mt_index: bigint
                           }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  agentOpenDispute(context: __compactRuntime.CircuitContext<PS>,
                   dealId_0: bigint,
                   idx_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  organizerOpenDispute(context: __compactRuntime.CircuitContext<PS>,
                       dealId_0: bigint,
                       idx_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterRelease(context: __compactRuntime.CircuitContext<PS>,
                 dealId_0: bigint,
                 idx_0: bigint,
                 spendCoin_0: { nonce: Uint8Array,
                                color: Uint8Array,
                                value: bigint,
                                mt_index: bigint
                              }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterRefund(context: __compactRuntime.CircuitContext<PS>,
                dealId_0: bigint,
                idx_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterTimeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                       dealId_0: bigint,
                       idx_0: bigint,
                       spendCoin_0: { nonce: Uint8Array,
                                      color: Uint8Array,
                                      value: bigint,
                                      mt_index: bigint
                                    }): Promise<__compactRuntime.CircuitResults<PS, []>>;
}

export type PureCircuits = {
  agentCommitment(sk_0: Uint8Array, dealRef_0: Uint8Array): Uint8Array;
  organizerCommitment(sk_0: Uint8Array, dealRef_0: Uint8Array): Uint8Array;
  arbiterCommitment(sk_0: Uint8Array, dealRef_0: Uint8Array): Uint8Array;
  milestoneKey(dealId_0: bigint, idx_0: bigint): bigint;
}

export type Circuits<PS> = {
  agentCommitment(context: __compactRuntime.CircuitContext<PS>,
                  sk_0: Uint8Array,
                  dealRef_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  organizerCommitment(context: __compactRuntime.CircuitContext<PS>,
                      sk_0: Uint8Array,
                      dealRef_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  arbiterCommitment(context: __compactRuntime.CircuitContext<PS>,
                    sk_0: Uint8Array,
                    dealRef_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  milestoneKey(context: __compactRuntime.CircuitContext<PS>,
               dealId_0: bigint,
               idx_0: bigint): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
  createDeal(context: __compactRuntime.CircuitContext<PS>,
             dealRef_0: Uint8Array,
             count_0: bigint,
             organizerCommitmentInput_0: Uint8Array,
             arbiterCommitmentInput_0: Uint8Array,
             arbiterDeadline_0: bigint,
             agentPk_0: { bytes: Uint8Array },
             organizerPk_0: { bytes: Uint8Array }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  createMilestone(context: __compactRuntime.CircuitContext<PS>,
                  dealId_0: bigint,
                  amount_0: bigint,
                  deadline_0: bigint,
                  claimDeadline_0: bigint,
                  deposit_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  releaseMilestone(context: __compactRuntime.CircuitContext<PS>,
                   dealId_0: bigint,
                   idx_0: bigint,
                   spendCoin_0: { nonce: Uint8Array,
                                  color: Uint8Array,
                                  value: bigint,
                                  mt_index: bigint
                                }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  refundMilestone(context: __compactRuntime.CircuitContext<PS>,
                  dealId_0: bigint,
                  idx_0: bigint,
                  spendCoin_0: { nonce: Uint8Array,
                                 color: Uint8Array,
                                 value: bigint,
                                 mt_index: bigint
                               }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  timeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                dealId_0: bigint,
                idx_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  autoRelease(context: __compactRuntime.CircuitContext<PS>,
              dealId_0: bigint,
              idx_0: bigint,
              spendCoin_0: { nonce: Uint8Array,
                             color: Uint8Array,
                             value: bigint,
                             mt_index: bigint
                           }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  agentOpenDispute(context: __compactRuntime.CircuitContext<PS>,
                   dealId_0: bigint,
                   idx_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  organizerOpenDispute(context: __compactRuntime.CircuitContext<PS>,
                       dealId_0: bigint,
                       idx_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterRelease(context: __compactRuntime.CircuitContext<PS>,
                 dealId_0: bigint,
                 idx_0: bigint,
                 spendCoin_0: { nonce: Uint8Array,
                                color: Uint8Array,
                                value: bigint,
                                mt_index: bigint
                              }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterRefund(context: __compactRuntime.CircuitContext<PS>,
                dealId_0: bigint,
                idx_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  arbiterTimeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                       dealId_0: bigint,
                       idx_0: bigint,
                       spendCoin_0: { nonce: Uint8Array,
                                      color: Uint8Array,
                                      value: bigint,
                                      mt_index: bigint
                                    }): Promise<__compactRuntime.CircuitResults<PS, []>>;
}

export type Ledger = {
  deals: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): { dealRef: Uint8Array,
                             agentCommitment: Uint8Array,
                             organizerCommitment: Uint8Array,
                             arbiterCommitment: Uint8Array,
                             count: bigint,
                             created: bigint,
                             arbiterDeadline: bigint,
                             agentPk: { bytes: Uint8Array },
                             organizerPk: { bytes: Uint8Array }
                           };
    [Symbol.iterator](): Iterator<[bigint, { dealRef: Uint8Array,
  agentCommitment: Uint8Array,
  organizerCommitment: Uint8Array,
  arbiterCommitment: Uint8Array,
  count: bigint,
  created: bigint,
  arbiterDeadline: bigint,
  agentPk: { bytes: Uint8Array },
  organizerPk: { bytes: Uint8Array }
}]>
  };
  milestones: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): { amount: bigint,
                             state: bigint,
                             deadline: bigint,
                             claimDeadline: bigint,
                             coinNonce: Uint8Array,
                             coinColor: Uint8Array
                           };
    [Symbol.iterator](): Iterator<[bigint, { amount: bigint,
  state: bigint,
  deadline: bigint,
  claimDeadline: bigint,
  coinNonce: Uint8Array,
  coinColor: Uint8Array
}]>
  };
  readonly nextDealId: bigint;
}

export type ContractReferenceLocations = any;

export declare const contractReferenceLocations : ContractReferenceLocations;

export declare class Contract<PS = any, W extends Witnesses<PS> = Witnesses<PS>> {
  witnesses: W;
  circuits: Circuits<PS>;
  impureCircuits: ImpureCircuits<PS>;
  provableCircuits: ProvableCircuits<PS>;
  constructor(witnesses: W);
  initialState(context: __compactRuntime.ConstructorContext<PS>): Promise<__compactRuntime.ConstructorResult<PS>>;
}

export declare function ledger(state: __compactRuntime.StateValue | __compactRuntime.ChargedState): Ledger;
export declare const pureCircuits: PureCircuits;
export declare const expectedVk: Record<string, string>;
