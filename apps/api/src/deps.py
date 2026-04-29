"""FastAPI dependency injection registry.

Auth/tenancy deps land in phase 0C (current_tenancy, require_role,
require_empresa_access). DB session dep lands once SessionLocal is wired
to a real database in phase 0B.
"""
