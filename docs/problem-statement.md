# Problem Statement

## Background

Public-safety CCTV in India is rapidly expanding, but it is owned by many different bodies: state police, transport/RTO, municipal corporations and private operators. Each runs its own cameras, video management software and storage, with different codecs, stream formats and access rules.

## The Problem

When a person is reported missing or a suspect is wanted, there is no way to ask "where was this person seen?" across all of those cameras. Operators open one system at a time and scrub footage by eye. A single search across a handful of cameras can take hours, and searching across departments usually means phone calls and formal requests. By the time a match is found the person has moved on.

## Who is Affected

- **Control-room operators and investigating officers** who must locate a specific person quickly using footage from multiple departments.
- **Families of missing persons**, especially children and vulnerable adults, for whom the first hours matter most.
- **Department administrators** who cannot tell which areas lack coverage or which cameras are down, because there is no single registry.

## Why It Matters

- **Response time:** manual footage review scales linearly with the number of cameras and hours. It does not scale to a city.
- **Missed sightings:** a person captured on camera is only useful if someone actually finds that frame.
- **Blind spots:** without a unified registry, coverage gaps and offline cameras go unnoticed until an incident exposes them.

## Why Existing Solutions Fall Short

- **Per-vendor VMS tools** search only their own cameras and usually only by time and location, not by who is in the frame.
- **Manual review** is slow, tiring and error-prone, and it does not work across departments.
- **Generic face-recognition demos** work on a single image or video but do not handle live multi-camera ingestion, watchlist alerting, back-pressure, or data retention. Netra is built as the missing platform layer: registry, ingestion, recognition, alerts and search working together, with unmatched detections auto-deleted after 48 hours to limit privacy exposure.