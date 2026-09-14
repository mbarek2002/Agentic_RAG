from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from src.models.paper import Paper
from src.schemas.arxiv.paper import PaperCreate


class PaperRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, paper: PaperCreate) -> Paper:
        db_paper = Paper(**paper.model_dump())
        self.session.add(db_paper)
        self.session.commit()
        self.session.refresh(db_paper)
        return db_paper

    def get_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        stmt = select(Paper).where(Paper.arxiv_id == arxiv_id)
        return self.session.scalar(stmt)

    def get_by_id(self, paper_id: UUID) -> Optional[Paper]:
        stmt = select(Paper).where(Paper.id == paper_id)
        return self.session.scalar(stmt)

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Paper]:
        stmt = select(Paper).order_by(Paper.published_date.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def get_count(self) -> int:
        stmt = select(func.count()).select_from(Paper)
        return self.session.scalar(stmt) or 0

    def update(self, paper: Paper) -> Paper:
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(paper)
        return paper

    def upsert(self, paper_create: PaperCreate) -> Paper:
        existing_paper = self.get_by_arxiv_id(paper_create.arxiv_id)
        if existing_paper:
            for key, value in paper_create.model_dump(exclude_unset=True).items():
                setattr(existing_paper, key, value)
            return self.update(existing_paper)
        return self.create(paper_create)

    def get_processed_papers(self, limit: int = 100, offset: int = 0) -> List[Paper]:
        stmt = (
            select(Paper)
            .where(Paper.pdf_processed.is_(True))
            .order_by(Paper.published_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def get_unprocessed_papers(self, limit: int = 100, offset: int = 0) -> List[Paper]:
        stmt = (
            select(Paper)
            .where(Paper.pdf_processed.is_(False))
            .order_by(Paper.published_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def get_papers_with_raw_text(self, limit: int = 100, offset: int = 0) -> List[Paper]:
        stmt = (
            select(Paper)
            .where(Paper.raw_text.is_not(None))
            .order_by(Paper.published_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def get_processing_stats(self) -> Dict[str, Any]:
        total = self.get_count()

        processed_stmt = select(func.count()).select_from(Paper).where(Paper.pdf_processed.is_(True))
        processed = self.session.scalar(processed_stmt) or 0

        with_text_stmt = select(func.count()).select_from(Paper).where(Paper.raw_text.is_not(None))
        with_text = self.session.scalar(with_text_stmt) or 0

        return {
            "total_papers": total,
            "processed_papers": processed,
            "unprocessed_papers": total - processed,
            "papers_with_raw_text": with_text,
            "processing_rate": round(processed / total, 4) if total else 0.0,
            "extraction_rate": round(with_text / total, 4) if total else 0.0,
        }
