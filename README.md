# Find Your Job v1.0

Find Your Job is a job-matching and application workflow product built to help candidates move from search to submission in one place.

Public app:
- https://findyourjob-lusmh75vq-ericyaos-projects.vercel.app

## What It Does

Find Your Job combines five workflow stages into one product:

1. Research jobs from live sources
2. Score job fit and explain why each role matches
3. Draft application materials
4. Prepare browser-driven application execution
5. Gate risky submissions behind user confirmation

The product is designed to reduce repetitive manual work while keeping the user in control of final applications.

## What Users See

The current product experience focuses on a clean, concise flow:

- enter target titles
- enter preferred locations
- provide application form details such as name, email, phone number, and years of experience
- upload a resume once
- choose whether auto-submit is enabled
- review matched jobs returned by the system

The search process itself is intentionally hidden from the user-facing interface. The UI is designed to surface outcomes, not internal workflow noise.

## Core Product Capabilities

- Multi-source job discovery across LinkedIn, Lever, and Greenhouse
- Fit scoring with rationale and skill-gap highlighting
- Tailored application drafting
- Resume upload and storage-backed processing
- Browser automation support for supported application flows
- English and Chinese interface toggle
- Review gating before risky or final submission steps

## Current Public Version

This repository now represents `v1.0`.

`v1.0` includes:

- public web frontend
- deployed backend API
- deployed worker
- live research pipeline
- resume upload flow
- job result rendering
- bilingual interface switch

## Product Direction

Find Your Job is built for candidates who want a more operational way to manage job applications:

- less copy-paste
- fewer repeated form fills
- clearer fit decisions
- a controlled path from discovery to apply

## Technical Documentation

All architecture, deployment, and environment setup details have been moved to:

- [TECHNICAL.md](/Users/ericyao/agent_projects/Find_Your_Job/TECHNICAL.md)
