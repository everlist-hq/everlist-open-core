import type * as __compactRuntime from '@midnight-ntwrk/compact-runtime';

export type Witnesses<PS> = {
  agentSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
  organizerSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
}

export type ImpureCircuits<PS> = {
  createEscrow(context: __compactRuntime.CircuitContext<PS>,
               amount_0: bigint,
               organizerCommitmentInput_0: Uint8Array,
               bookingRef_0: Uint8Array,
               deadline_0: bigint,
               claimDeadline_0: bigint,
               deposit_0: { nonce: Uint8Array, color: Uint8Array, value: bigint
                          },
               agentPk_0: { bytes: Uint8Array },
               organizerPk_0: { bytes: Uint8Array }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  releaseEscrow(context: __compactRuntime.CircuitContext<PS>,
                escrowId_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  refundEscrow(context: __compactRuntime.CircuitContext<PS>,
               escrowId_0: bigint,
               spendCoin_0: { nonce: Uint8Array,
                              color: Uint8Array,
                              value: bigint,
                              mt_index: bigint
                            }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  timeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                escrowId_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  mutualRefund(context: __compactRuntime.CircuitContext<PS>,
               escrowId_0: bigint,
               returnCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  autoRelease(context: __compactRuntime.CircuitContext<PS>,
              escrowId_0: bigint,
              spendCoin_0: { nonce: Uint8Array,
                             color: Uint8Array,
                             value: bigint,
                             mt_index: bigint
                           }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isHeld(context: __compactRuntime.CircuitContext<PS>, escrowId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
}

export type ProvableCircuits<PS> = {
  createEscrow(context: __compactRuntime.CircuitContext<PS>,
               amount_0: bigint,
               organizerCommitmentInput_0: Uint8Array,
               bookingRef_0: Uint8Array,
               deadline_0: bigint,
               claimDeadline_0: bigint,
               deposit_0: { nonce: Uint8Array, color: Uint8Array, value: bigint
                          },
               agentPk_0: { bytes: Uint8Array },
               organizerPk_0: { bytes: Uint8Array }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  releaseEscrow(context: __compactRuntime.CircuitContext<PS>,
                escrowId_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  refundEscrow(context: __compactRuntime.CircuitContext<PS>,
               escrowId_0: bigint,
               spendCoin_0: { nonce: Uint8Array,
                              color: Uint8Array,
                              value: bigint,
                              mt_index: bigint
                            }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  timeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                escrowId_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  mutualRefund(context: __compactRuntime.CircuitContext<PS>,
               escrowId_0: bigint,
               returnCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  autoRelease(context: __compactRuntime.CircuitContext<PS>,
              escrowId_0: bigint,
              spendCoin_0: { nonce: Uint8Array,
                             color: Uint8Array,
                             value: bigint,
                             mt_index: bigint
                           }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isHeld(context: __compactRuntime.CircuitContext<PS>, escrowId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
}

export type PureCircuits = {
  agentCommitment(sk_0: Uint8Array): Uint8Array;
  organizerCommitment(sk_0: Uint8Array): Uint8Array;
}

export type Circuits<PS> = {
  agentCommitment(context: __compactRuntime.CircuitContext<PS>, sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  organizerCommitment(context: __compactRuntime.CircuitContext<PS>,
                      sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  createEscrow(context: __compactRuntime.CircuitContext<PS>,
               amount_0: bigint,
               organizerCommitmentInput_0: Uint8Array,
               bookingRef_0: Uint8Array,
               deadline_0: bigint,
               claimDeadline_0: bigint,
               deposit_0: { nonce: Uint8Array, color: Uint8Array, value: bigint
                          },
               agentPk_0: { bytes: Uint8Array },
               organizerPk_0: { bytes: Uint8Array }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  releaseEscrow(context: __compactRuntime.CircuitContext<PS>,
                escrowId_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  refundEscrow(context: __compactRuntime.CircuitContext<PS>,
               escrowId_0: bigint,
               spendCoin_0: { nonce: Uint8Array,
                              color: Uint8Array,
                              value: bigint,
                              mt_index: bigint
                            }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  timeoutRefund(context: __compactRuntime.CircuitContext<PS>,
                escrowId_0: bigint,
                spendCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  mutualRefund(context: __compactRuntime.CircuitContext<PS>,
               escrowId_0: bigint,
               returnCoin_0: { nonce: Uint8Array,
                               color: Uint8Array,
                               value: bigint,
                               mt_index: bigint
                             }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  autoRelease(context: __compactRuntime.CircuitContext<PS>,
              escrowId_0: bigint,
              spendCoin_0: { nonce: Uint8Array,
                             color: Uint8Array,
                             value: bigint,
                             mt_index: bigint
                           }): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isHeld(context: __compactRuntime.CircuitContext<PS>, escrowId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
}

export type Ledger = {
  escrows: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): { amount: bigint,
                             agentCommitment: Uint8Array,
                             organizerCommitment: Uint8Array,
                             state: bigint,
                             bookingRef: Uint8Array,
                             deadline: bigint,
                             claimDeadline: bigint,
                             coinNonce: Uint8Array,
                             coinColor: Uint8Array
                           };
    [Symbol.iterator](): Iterator<[bigint, { amount: bigint,
  agentCommitment: Uint8Array,
  organizerCommitment: Uint8Array,
  state: bigint,
  bookingRef: Uint8Array,
  deadline: bigint,
  claimDeadline: bigint,
  coinNonce: Uint8Array,
  coinColor: Uint8Array
}]>
  };
  readonly nextId: bigint;
  agentPks: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): { bytes: Uint8Array };
    [Symbol.iterator](): Iterator<[bigint, { bytes: Uint8Array }]>
  };
  organizerPks: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): { bytes: Uint8Array };
    [Symbol.iterator](): Iterator<[bigint, { bytes: Uint8Array }]>
  };
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
