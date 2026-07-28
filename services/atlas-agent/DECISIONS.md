# Atlas Agent Decisions

## Overview

This document records key architectural decisions made for Atlas Agent.

## Core Principles

### Orchestration, Not Ownership

Atlas Agent orchestrates engineering workflows but does not own the underlying
tools or systems. It coordinates with other services rather than replacing them.

### Atlas Core is Authoritative

Atlas Core remains the authoritative source of Atlas system state.
All information accessed by Atlas Agent comes through supported Atlas Core APIs.

### API-Only Atlas State Access

Atlas Agent accesses Atlas state only through supported APIs.
Direct database access is not permitted.

### Engines Consume Normalized Typed Context

Each engine receives a normalized, typed context from the Context Engine.
Engines do not call Atlas Core independently.

### Write Operations and External Commands Require Approval

All write operations and external command execution require human approval
before proceeding. This ensures that no changes are made without proper oversight.

### Model Providers and Tool Executors Are Replaceable

The underlying model providers and tool executors remain replaceable.
This allows for flexibility in implementation while maintaining the overall architecture.
