import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime, timedelta

# Loglar sozlamasi
logging.basicConfig(level=logging.INFO)

# Bot tokenini environment'dan olish
API_TOKEN = os.getenv("API_TOKEN")

# SQLAlchemy ma'lumotlar bazasi sozlamalari
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, echo=True)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Bot va Dispatcher yaratish
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Task jadvallari uchun model
class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    description = Column(String, index=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime)

    def __repr__(self):
        return f"{self.description} (Boshlanish: {self.start_date}, Tugash: {self.end_date})"

# Ma'lumotlar bazasini yaratish funksiyasi
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# /start komandasi uchun handler
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Salom! Botga xush kelibsiz! Sizning to-do ro'yxatingizni boshqaraman.\n"
                         "Vazifa qo'shish uchun: /add <vazifa> <boshlanish_sana> <tugash_sana>\n"
                         "Vazifalar ro'yxatini ko'rish uchun: /list\n"
                         "Vazifani o'chirish uchun: /delete <raqam>\n"
                         "Muddati o'tgan vazifalarni ko'rish uchun: /overdue\n"
                         "Bugungi darslarni ko'rish uchun: /today\n"
                         "Bir haftalik darslarni ko'rish uchun: /week\n"
                         "Bir oylik darslarni ko'rish uchun: /month")

# /add komandasi uchun handler - vazifa qo'shish
@dp.message(Command("add"))
async def add_task(message: types.Message):
    args = message.text.split()[1:]  # Birinchi so'zni (buyruq) tashlab ketamiz
    if len(args) < 3:
        await message.answer("Iltimos, vazifani, boshlanish sanasini (YYYY-MM-DD) va tugash sanasini (YYYY-MM-DD) kiriting.")
        return

    description = args[0]
    start_date = args[1]
    end_date = args[2]

    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        await message.answer("Sanasini to'g'ri formatda kiriting (YYYY-MM-DD).")
        return

    async with SessionLocal() as session:
        task = Task(user_id=message.from_user.id, description=description, start_date=start_date, end_date=end_date)
        session.add(task)
        await session.commit()
    
    await message.answer(f"Vazifa qo'shildi: {task}")

# /list komandasi uchun handler - vazifalar ro'yxatini ko'rish
@dp.message(Command("list"))
async def list_tasks(message: types.Message):
    async with SessionLocal() as session:
        result = await session.execute(
            Task.__table__.select().where(Task.user_id == message.from_user.id)
        )
        tasks = result.scalars().all()
    
    if not tasks:
        await message.answer("Sizning to-do ro'yxatingiz bo'sh.")
        return

    response = "\n".join([f"{idx+1}. {task}" for idx, task in enumerate(tasks)])
    await message.answer(f"Sizning to-do ro'yxatingiz:\n{response}")

# /delete komandasi uchun handler - vazifani o'chirish
@dp.message(Command("delete"))
async def delete_task(message: types.Message):
    try:
        task_num = int(message.text.split()[1])
    except (ValueError, IndexError):
        await message.answer("Iltimos, to'g'ri vazifa raqamini kiriting.")
        return

    async with SessionLocal() as session:
        result = await session.execute(
            Task.__table__.select().where(Task.user_id == message.from_user.id)
        )
        tasks = result.scalars().all()

        if task_num <= 0 or task_num > len(tasks):
            await message.answer("Noto'g'ri vazifa raqami.")
            return
        
        task = tasks[task_num - 1]
        await session.delete(task)
        await session.commit()
    
    await message.answer(f"Vazifa o'chirildi: {task}")

# /overdue komandasi uchun handler - muddati o'tgan vazifalar
@dp.message(Command("overdue"))
async def overdue_tasks(message: types.Message):
    now = datetime.now()

    async with SessionLocal() as session:
        result = await session.execute(
            Task.__table__.select().where(Task.user_id == message.from_user.id, Task.end_date < now)
        )
        overdue = result.scalars().all()
    
    if not overdue:
        await message.answer("Muddati o'tgan vazifalar yo'q.")
        return

    response = "\n".join([f"{idx+1}. {task}" for idx, task in enumerate(overdue)])
    await message.answer(f"Muddati o'tgan vazifalar:\n{response}")

# /today komandasi uchun handler - bugungi darslar
@dp.message(Command("today"))
async def today_tasks(message: types.Message):
    now = datetime.now().date()

    async with SessionLocal() as session:
        result = await session.execute(
            Task.__table__.select().where(
                Task.user_id == message.from_user.id,
                Task.start_date <= datetime.combine(now, datetime.min.time()),
                Task.end_date >= datetime.combine(now, datetime.max.time())
            )
        )
        today_tasks = result.scalars().all()
    
    if not today_tasks:
        await message.answer("Bugungi darslar yo'q.")
        return

    response = "\n".join([f"{idx+1}. {task}" for idx, task in enumerate(today_tasks)])
    await message.answer(f"Bugungi darslar:\n{response}")

# Botni ishga tushirish
if __name__ == '__main__':
    import asyncio
    # Ma'lumotlar bazasini yaratish
    asyncio.run(init_db())
    dp.run_polling(bot)
