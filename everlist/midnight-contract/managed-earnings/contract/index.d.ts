import type * as __compactRuntime from '@midnight-ntwrk/compact-runtime';

export type Witnesses<PS> = {
  organizerSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
  earningsIssuerSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
}

export type ImpureCircuits<PS> = {
  initializeEarningsIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  registerOrganizer(context: __compactRuntime.CircuitContext<PS>,
                    orgComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, []>>;
  recordEarnings(context: __compactRuntime.CircuitContext<PS>,
                 orgComm_0: Uint8Array,
                 volume_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveEarningsFloor(context: __compactRuntime.CircuitContext<PS>,
                     minSettlements_0: bigint,
                     minVolume_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  getEarnings(context: __compactRuntime.CircuitContext<PS>,
              orgComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, { settledCount: bigint,
                                                                                    totalVolume: bigint
                                                                                  }>>;
}

export type ProvableCircuits<PS> = {
  initializeEarningsIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  registerOrganizer(context: __compactRuntime.CircuitContext<PS>,
                    orgComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, []>>;
  recordEarnings(context: __compactRuntime.CircuitContext<PS>,
                 orgComm_0: Uint8Array,
                 volume_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveEarningsFloor(context: __compactRuntime.CircuitContext<PS>,
                     minSettlements_0: bigint,
                     minVolume_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  getEarnings(context: __compactRuntime.CircuitContext<PS>,
              orgComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, { settledCount: bigint,
                                                                                    totalVolume: bigint
                                                                                  }>>;
}

export type PureCircuits = {
  organizerEarningsCommitment(sk_0: Uint8Array): Uint8Array;
  earningsIssuerCommitment(sk_0: Uint8Array): Uint8Array;
}

export type Circuits<PS> = {
  organizerEarningsCommitment(context: __compactRuntime.CircuitContext<PS>,
                              sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  earningsIssuerCommitment(context: __compactRuntime.CircuitContext<PS>,
                           sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  initializeEarningsIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  registerOrganizer(context: __compactRuntime.CircuitContext<PS>,
                    orgComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, []>>;
  recordEarnings(context: __compactRuntime.CircuitContext<PS>,
                 orgComm_0: Uint8Array,
                 volume_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveEarningsFloor(context: __compactRuntime.CircuitContext<PS>,
                     minSettlements_0: bigint,
                     minVolume_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  getEarnings(context: __compactRuntime.CircuitContext<PS>,
              orgComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, { settledCount: bigint,
                                                                                    totalVolume: bigint
                                                                                  }>>;
}

export type Ledger = {
  earningsIssuer: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): Uint8Array;
    [Symbol.iterator](): Iterator<[bigint, Uint8Array]>
  };
  organizerEarnings: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: Uint8Array): boolean;
    lookup(key_0: Uint8Array): { settledCount: bigint, totalVolume: bigint };
    [Symbol.iterator](): Iterator<[Uint8Array, { settledCount: bigint, totalVolume: bigint }]>
  };
  readonly earningsCount: bigint;
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
