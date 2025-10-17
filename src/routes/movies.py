from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from datetime import date, timedelta

from database.session_postgresql import get_db
from database.models import (
    MovieModel,
    GenreModel,
    ActorModel,
    CountryModel,
    LanguageModel,
)
from schemas.movies import (
    MovieShort,
    MovieFull,
    MovieCreate,
    MovieUpdate,
    MoviesListResponse,
)

router = APIRouter(prefix="/movies", tags=["Movies"])


@router.get("/", response_model=MoviesListResponse)
async def list_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(func.count()).select_from(MovieModel))
    total_items = result.scalar_one()

    total_pages = (total_items + per_page - 1) // per_page
    if page > total_pages and total_items > 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page

    result = await db.execute(
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    movies = result.scalars().all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    base_url = "/movies/"
    prev_page = (
        f"{base_url}?page={page-1}&per_page={per_page}" if page > 1 else None
    )
    next_page = (
        f"{base_url}?page={page+1}&per_page={per_page}"
        if page < total_pages
        else None
    )

    return MoviesListResponse(
        movies=movies,
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )


@router.get("/{movie_id}/", response_model=MovieFull)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            MovieModel.country,
            MovieModel.genres,
            MovieModel.actors,
            MovieModel.languages,
        )
    )
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )
    return movie


@router.post("/", response_model=MovieFull, status_code=status.HTTP_201_CREATED)
async def create_movie(movie_data: MovieCreate, db: AsyncSession = Depends(get_db)):
    # Duplicate check
    existing = await db.execute(
        select(MovieModel).where(
            MovieModel.name == movie_data.name,
            MovieModel.date == movie_data.date,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}' and release date '{movie_data.date}' already exists.",
        )

    # Validate date not > 1 year in future
    if movie_data.date > date.today() + timedelta(days=365):
        raise HTTPException(status_code=400, detail="Invalid input data.")

    # Country
    country = None
    if movie_data.country:
        result = await db.execute(
            select(CountryModel).where(CountryModel.code == movie_data.country)
        )
        country = result.scalar_one_or_none()
        if not country:
            country = CountryModel(code=movie_data.country, name=None)
            db.add(country)
            await db.flush()

    # Helper to get or create many-to-many items
    async def get_or_create(model, names: list[str], field="name"):
        objs = []
        for name in names:
            res = await db.execute(select(model).where(getattr(model, field) == name))
            obj = res.scalar_one_or_none()
            if not obj:
                obj = model(name=name)
                db.add(obj)
                await db.flush()
            objs.append(obj)
        return objs

    genres = await get_or_create(GenreModel, movie_data.genres)
    actors = await get_or_create(ActorModel, movie_data.actors)
    languages = await get_or_create(LanguageModel, movie_data.languages)

    new_movie = MovieModel(
        name=movie_data.name,
        date=movie_data.date,
        score=movie_data.score,
        overview=movie_data.overview,
        status=movie_data.status,
        budget=movie_data.budget,
        revenue=movie_data.revenue,
        country_id=country.id if country else None,
        genres=genres,
        actors=actors,
        languages=languages,
    )

    db.add(new_movie)
    await db.commit()
    await db.refresh(new_movie)

    return new_movie


@router.patch("/{movie_id}/")
async def update_movie(movie_id: int, data: MovieUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    if data.score is not None and not (0 <= data.score <= 100):
        raise HTTPException(status_code=400, detail="Invalid input data.")
    if data.budget is not None and data.budget < 0:
        raise HTTPException(status_code=400, detail="Invalid input data.")
    if data.revenue is not None and data.revenue < 0:
        raise HTTPException(status_code=400, detail="Invalid input data.")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(movie, field, value)

    await db.commit()
    return {"detail": "Movie updated successfully."}


@router.delete("/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )
    await db.delete(movie)
    await db.commit()
