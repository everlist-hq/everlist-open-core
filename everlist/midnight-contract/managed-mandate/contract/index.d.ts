import type * as __compactRuntime from '@midnight-ntwrk/compact-runtime';

export type Witnesses<PS> = {
  mandateSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
  mandateCap(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, bigint];
  mandateCategory(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, bigint];
  revokeSecretKey(context: __compactRuntime.WitnessContext<Ledger, PS>): [PS, Uint8Array];
}

export type ImpureCircuits<PS> = {
  issueMandate(context: __compactRuntime.CircuitContext<PS>,
               actionComm_0: Uint8Array,
               revokeComm_0: Uint8Array,
               expiry_0: bigint): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
  authorize(context: __compactRuntime.CircuitContext<PS>,
            mandateId_0: bigint,
            amount_0: bigint,
            actionCategory_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  revokeMandate(context: __compactRuntime.CircuitContext<PS>,
                mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isRevoked(context: __compactRuntime.CircuitContext<PS>, mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
  useCount(context: __compactRuntime.CircuitContext<PS>, mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
}

export type ProvableCircuits<PS> = {
  issueMandate(context: __compactRuntime.CircuitContext<PS>,
               actionComm_0: Uint8Array,
               revokeComm_0: Uint8Array,
               expiry_0: bigint): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
  authorize(context: __compactRuntime.CircuitContext<PS>,
            mandateId_0: bigint,
            amount_0: bigint,
            actionCategory_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  revokeMandate(context: __compactRuntime.CircuitContext<PS>,
                mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isRevoked(context: __compactRuntime.CircuitContext<PS>, mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
  useCount(context: __compactRuntime.CircuitContext<PS>, mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
}

export type PureCircuits = {
  mandateCommitment(sk_0: Uint8Array, cap_0: bigint, category_0: bigint): Uint8Array;
  revokeCommitment(sk_0: Uint8Array): Uint8Array;
}

export type Circuits<PS> = {
  mandateCommitment(context: __compactRuntime.CircuitContext<PS>,
                    sk_0: Uint8Array,
                    cap_0: bigint,
                    category_0: bigint): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  revokeCommitment(context: __compactRuntime.CircuitContext<PS>,
                   sk_0: Uint8Array): Promise<__compactRuntime.CircuitResults<PS, Uint8Array>>;
  issueMandate(context: __compactRuntime.CircuitContext<PS>,
               actionComm_0: Uint8Array,
               revokeComm_0: Uint8Array,
               expiry_0: bigint): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
  authorize(context: __compactRuntime.CircuitContext<PS>,
            mandateId_0: bigint,
            amount_0: bigint,
            actionCategory_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  revokeMandate(context: __compactRuntime.CircuitContext<PS>,
                mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, []>>;
  isRevoked(context: __compactRuntime.CircuitContext<PS>, mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, boolean>>;
  useCount(context: __compactRuntime.CircuitContext<PS>, mandateId_0: bigint): Promise<__compactRuntime.CircuitResults<PS, bigint>>;
}

export type Ledger = {
  mandates: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): { actionCommitment: Uint8Array,
                             revokeCommitment: Uint8Array,
                             expiry: bigint,
                             revoked: boolean
                           };
    [Symbol.iterator](): Iterator<[bigint, { actionCommitment: Uint8Array,
  revokeCommitment: Uint8Array,
  expiry: bigint,
  revoked: boolean
}]>
  };
  uses: {
    isEmpty(): boolean;
    size(): bigint;
    member(key_0: bigint): boolean;
    lookup(key_0: bigint): bigint;
    [Symbol.iterator](): Iterator<[bigint, bigint]>
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
