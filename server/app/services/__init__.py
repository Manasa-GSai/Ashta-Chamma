"""Service layer — business logic and orchestration.

Services receive dependencies through constructor injection and coordinate
repositories, external providers, and domain rules.  They contain zero
HTTP-layer concerns (no request/response objects).
"""
