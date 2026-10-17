import type * as __compactRuntime from '@midnight-ntwrk/compact-runtime';

export type Witnesses<PS> = {
  agentSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
  issuerSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
}

export type ImpureCircuits<PS> = {
  initializeIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  registerAgent(context: __compactRuntime.CircuitContext<PS>,
                agentComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, []>>;
  recordSettlement(context: __compactRuntime.CircuitContext<PS>,
                   agentComm_0: Uint8Array,
                   volume_0: bigint,
                   rating_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveReputation(context: __compactRuntime.CircuitContext<PS>,
                  minSettlements_0: bigint,
                  minVolume_0: bigint,
                  minAvgRatingX10_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  getStats(context: __compactRuntime.CircuitContext<PS>, agentComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, { settledCount: bigint,
                                                                                                                                 totalVolume: bigint,
                                                                                                                                 ratingSum: bigint,
                                                                                                                                 ratingCount: bigint
                                                                                                                               }>>;
}

export type ProvableCircuits<PS> = {
  initializeIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  registerAgent(context: __compactRuntime.CircuitContext<PS>,
                agentComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, []>>;
  recordSettlement(context: __compactRuntime.CircuitContext<PS>,
                   agentComm_0: Uint8Array,
                   volume_0: bigint,
                   rating_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveReputation(context: __compactRuntime.CircuitContext<PS>,
                  minSettlements_0: bigint,
                  minVolume_0: bigint,
                  minAvgRatingX10_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  getStats(context: __compactRuntime.CircuitContext<PS>, agentComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, { settledCount: bigint,
                                                                                                                                 totalVolume: bigint,
                                                                                                                                 ratingSum: bigint,
                                                                                                                                 ratingCount: bigint
                                                                                                                               }>>;
}

export type PureCircuits = {
  agentReputationCommitment(sk_0: Uint8Array): Uint8Array;
  issuerCommitment(sk_0: Uint8Array): Uint8Array;
}

export type Circuits<PS> = {
  agentReputationCommitment(context: __compactRuntime.CircuitContext<PS>,
                            sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  issuerCommitment(context: __compactRuntime.CircuitContext<PS>,
                   sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  initializeIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  registerAgent(context: __compactRuntime.CircuitContext<PS>,
                agentComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, []>>;
  recordSettlement(context: __compactRuntime.CircuitContext<PS>,
                   agentComm_0: Uint8Array,
                   volume_0: bigint,
                   rating_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveReputation(context: __compactRuntime.CircuitContext<PS>,
                  minSettlements_0: bigint,
                  minVolume_0: bigint,
                  minAvgRatingX10_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  getStats(context: __compactRuntime.CircuitContext<PS>, agentComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, { settledCount: bigint,
                                                                                                                                 totalVolume: bigint,
                                                                                                                                 ratingSum: bigint,
                                                                                                                                 ratingCount: bigint
                                                                                                                               }>>;
}

export type Ledger = {
  issuer: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): Uint8Array;
    [Symbol.iterator](): Iterator<[bigint, Uint8Array]>
  };
  reputation: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: Uint8Array): boolean;
    lookup(key_0: Uint8Array): { settledCount: bigint,
                                 totalVolume: bigint,
                                 ratingSum: bigint,
                                 ratingCount: bigint
                               };
    [Symbol.iterator](): Iterator<[Uint8Array, { settledCount: bigint,
  totalVolume: bigint,
  ratingSum: bigint,
  ratingCount: bigint
}]>
  };
  readonly settlementCount: bigint;
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
