from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload, joinedload
from datetime import date, timedelta
from typing import List
from database import get_db
from database.models import MovieModel, GenreModel, ActorModel, CountryModel, LanguageModel
from schemas.movies import MovieFull, MovieCreate, MovieUpdate, MoviesListResponse

router = APIRouter(prefix="/movies", tags=["Movies"])


@router.get("/", response_model=MoviesListResponse)
async def list_movies(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20),
        db: AsyncSession = Depends(get_db),
):
    total_items = (await db.execute(select(func.count(MovieModel.id)))).scalar_one()
    total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 0

    if total_items == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No movies found.")

    offset = (page - 1) * per_page

    if page > total_pages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No movies found on this page.")

    result = await db.execute(
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
        .options(
            joinedload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )
    movies = result.scalars().all()

    base_url = "/theater/movies/"
    prev_page = f"{base_url}?page={page - 1}&per_page={per_page}" if page > 1 else None
    next_page = f"{base_url}?page={page + 1}&per_page={per_page}" if page < total_pages else None

    movies_data = [MovieFull.model_validate(m, from_attributes=True) for m in movies]

    return MoviesListResponse(
        movies=movies_data,
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
            joinedload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie with the given ID was not found.")

    return MovieFull.model_validate(movie, from_attributes=True)


@router.post("/", response_model=MovieFull, status_code=status.HTTP_201_CREATED)
async def create_movie(movie_data: MovieCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(MovieModel).where(
            MovieModel.name == movie_data.name,
            MovieModel.date == movie_data.date,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A movie with the name '{movie_data.name}' and release date '{movie_data.date}' already exists.",
        )

    if movie_data.date > date.today() + timedelta(days=365):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input data.")

    # Country
    country = None
    if movie_data.country:
        result = await db.execute(select(CountryModel).where(CountryModel.code == movie_data.country))
        country = result.scalar_one_or_none()
        if not country:
            country = CountryModel(code=movie_data.country, name=None)
            db.add(country)
            await db.flush()

    async def get_or_create(model, names: List[str], field="name"):
        objs = []
        for name in names:
            res = await db.execute(select(model).where(getattr(model, field) == name))
            obj = res.scalar_one_or_none()
            if not obj:
                obj = model(**{field: name})
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
    await db.refresh(
        new_movie,
        attribute_names=["country", "genres", "actors", "languages"]
    )

    return MovieFull.model_validate(new_movie, from_attributes=True)


@router.patch("/{movie_id}/", response_model=MovieFull)
async def update_movie(movie_id: int, data: MovieUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            joinedload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie with the given ID was not found.")

    update_data = data.model_dump(exclude_unset=True, exclude_none=True)

    for field in ['country', 'genres', 'actors', 'languages']:
        if field in update_data:
            update_data.pop(field)

    for field, value in update_data.items():
        setattr(movie, field, value)

    db.add(movie)

    await db.flush()
    await db.commit()

    await db.refresh(
        movie,
        attribute_names=["country", "genres", "actors", "languages"]
    )

    return MovieFull.model_validate(movie, from_attributes=True)


@router.delete("/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie with the given ID was not found.")

    await db.delete(movie)
    await db.commit()
