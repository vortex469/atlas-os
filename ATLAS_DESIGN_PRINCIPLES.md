# Atlas Design Principles

Atlas is an intent-driven infrastructure operating system. Other tools show what is; Atlas understands what should be.

These principles guide the Provider Management Framework and future Atlas features. They describe the product direction Atlas should follow as Mission Control becomes the normal way to manage infrastructure intent.

## 1. Intent over state

Atlas evaluates whether observed infrastructure matches user intent.

A stopped resource is not automatically a problem. It becomes a problem only when Atlas knows the user expects that resource to be running. The same observed state can be healthy, unhealthy, or intentionally ignored depending on the user's declared intent.

## 2. Discover first

Providers should discover resources automatically.

Users should not manually maintain normal inventory. Atlas should connect to infrastructure providers, discover the resources they expose, and present those resources in Mission Control before asking users to define monitoring intent.

## 3. Ask once

Newly discovered resources enter Needs Review.

Atlas asks the user for intent and remembers the answer. After the user chooses an expectation, Atlas should apply that policy consistently instead of repeatedly asking about the same resource.

## 4. No YAML for normal users

Mission Control is the normal configuration interface.

Files remain available for advanced operators, automation, backup, and review, but routine provider configuration should not require editing YAML. Normal users should be able to express intent safely through Mission Control.

## 5. Consistent provider experience

Providers should expose a consistent management surface:

- Connection
- Discovery
- Resources
- Monitoring
- Actions
- Diagnostics

Each provider will have different capabilities, but users should not need to learn a different product model for every integration.

## 6. AI suggests; users decide

AI may identify patterns and recommend intent changes.

AI must not silently change policy. Atlas can explain that a resource is repeatedly stopped and suggest marking it Expected Stopped or Ignore, but the user must approve the change before Atlas updates monitoring policy.

## 7. Explain every warning

Every warning should show:

- Observed state
- Expected state
- Why the finding exists
- Available remediation

A finding should be understandable without reading source code or YAML. Users should be able to see what Atlas observed, what Atlas expected, why the two do not match, and what safe actions are available.

## 8. Safe by default

Infrastructure changes, destructive operations, and policy changes require approval.

Atlas should prefer read-only discovery and explanation before mutation. When a change is needed, Atlas should present the consequence clearly and require explicit user approval.

## 9. Learn without nagging

Atlas may notice repeated patterns and offer a one-time suggestion.

The system should help users reduce noise without becoming noise itself. If a resource is intentionally stopped over time, Atlas may suggest changing intent, but it should avoid repeatedly interrupting the user after that suggestion is addressed or dismissed.

## 10. One place to manage infrastructure

Mission Control should become the unified control plane across providers.

The long-term direction is that users discover resources, set intent, review findings, approve actions, inspect diagnostics, and understand infrastructure relationships from one consistent interface.

## Provider Management Framework direction

The Provider Management Framework is the planned product layer that applies these principles across Atlas providers. Its goal is to move provider management from file-first configuration to discoverable, reviewable, user-approved intent management in Mission Control.

Initial work should distinguish clearly between current behavior and planned behavior. Atlas already has provider discovery, findings, policy loading, and Mission Control visibility in several areas. The Provider Management Framework is the next major milestone that will make those capabilities consistent, editable, and understandable for normal users.
