"""Backward-compatible alias exporting PlannerPDFService as ReportLabPDFService."""

from app.services.pdf.planner_pdf_service import PlannerPDFService

ReportLabPDFService = PlannerPDFService

__all__ = ["PlannerPDFService", "ReportLabPDFService"]
