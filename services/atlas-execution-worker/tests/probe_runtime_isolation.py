"""Credential-free observation probe for an explicitly hardened container."""
import json

from atlas_execution_worker.isolation import observe_attestation

result = observe_attestation()
print(json.dumps({'observed':result.to_dict(),'activation_authorized':False,'model_invocations':0,'account_credentials_used':False},sort_keys=True))
