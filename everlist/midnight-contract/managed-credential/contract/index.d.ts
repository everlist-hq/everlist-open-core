import type * as __compactRuntime from '@midnight-ntwrk/compact-runtime';

export type Witnesses<PS> = {
  issuerSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
  holderSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
}

export type ImpureCircuits<PS> = {
  initializeIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  issueCredential(context: __compactRuntime.CircuitContext<PS>,
                  holderComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
  revokeCredential(context: __compactRuntime.CircuitContext<PS>,
                   credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveHolder(context: __compactRuntime.CircuitContext<PS>, credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isRevoked(context: __compactRuntime.CircuitContext<PS>, credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
}

export type ProvableCircuits<PS> = {
  initializeIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  issueCredential(context: __compactRuntime.CircuitContext<PS>,
                  holderComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
  revokeCredential(context: __compactRuntime.CircuitContext<PS>,
                   credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveHolder(context: __compactRuntime.CircuitContext<PS>, credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isRevoked(context: __compactRuntime.CircuitContext<PS>, credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
}

export type PureCircuits = {
  issuerCommitment(sk_0: Uint8Array): Uint8Array;
  holderCommitment(sk_0: Uint8Array): Uint8Array;
}

export type Circuits<PS> = {
  issuerCommitment(context: __compactRuntime.CircuitContext<PS>,
                   sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  holderCommitment(context: __compactRuntime.CircuitContext<PS>,
                   sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  initializeIssuer(context: __compactRuntime.CircuitContext<PS>): Promise<__compactRuntime.CircuitResults<PS, []>>;
  issueCredential(context: __compactRuntime.CircuitContext<PS>,
                  holderComm_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
  revokeCredential(context: __compactRuntime.CircuitContext<PS>,
                   credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  proveHolder(context: __compactRuntime.CircuitContext<PS>, credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isRevoked(context: __compactRuntime.CircuitContext<PS>, credId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
}

export type Ledger = {
  issuer: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): Uint8Array;
    [Symbol.iterator](): Iterator<[bigint, Uint8Array]>
  };
  holders: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): Uint8Array;
    [Symbol.iterator](): Iterator<[bigint, Uint8Array]>
  };
  revoked: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): boolean;
    [Symbol.iterator](): Iterator<[bigint, boolean]>
  };
  readonly nextId: bigint;
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
