import asyncpg
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder ,
    ContextTypes , 
    CommandHandler ,
    MessageHandler , 
    filters , 
    Application
)
import jdatetime


class DataBase:
    def __init__(self):
        self.user = "postgres"
        self.password = "S!fy"
        self.database= "tel_event_db"
        self.host = "localhost"
        self.conn = None
    

    async def user_exists(self , user_id) -> bool:
        query = "SELECT user_id FROM users WHERE user_id = $1"
        row = await self.conn.fetchrow(query , user_id)
        return row is not None  

    async def event_exists(self , user_id , event_name):
        query = """
        SELECT 1 FROM EVENTS
        WHERE (user_id) = $1 AND (event_name) = $2
        """
        row = await self.conn.fetchrow(query , user_id , event_name)
        return row is not None

    async def run(self):
        self.conn = await asyncpg.connect(
            user=self.user ,
            password= self.password ,
            database=self.database ,
            host=self.host
        )
        print("Database is connected...")

    async def insert_events(self , user_id , event_name):
        query = """
        INSERT INTO events (user_id, event_name)
        VALUES ($1, $2)
        """
        if await self.event_exists(user_id , event_name):
            print("Event already exists, skipping insert")
            return

        await self.conn.execute(query , user_id , event_name)
        print("inserted in events")
        return

    async def insert_users(self , user_id , username):
        query = """
        INSERT INTO users (user_id , username)
        VALUES ($1 , $2)
        ON CONFLICT (user_id) DO NOTHING
        """
        await self.conn.execute(query , user_id , username)
        print("inserted in users")

    async def show_user_events(self , user_id):
        query = """
        SELECT event_name, event_time
        FROM events
        WHERE user_id = $1
        ORDER BY event_time ASC
        """
        rows = await self.conn.fetch(query, user_id)
        
        if not rows:
            return "You have not added any events yet."
        
        upcoming = "Your upcoming event:\n\n"
        date_str = rows[0]["event_time"].strftime("%d/%m/%Y")
        delta = (rows[0]["event_time"].date() - datetime.now().date()).days
        upcoming += f"• {rows[0]['event_name']} - {date_str} (in {delta} days)\n\n\n\n"

        result = "Your events:\n\n"
        for row in rows:
            date_str = row["event_time"].strftime("%d/%m/%Y")
            result += f"• {row['event_name']} - {date_str}\n"

        result = upcoming + result
        return result

    async def remove_event(self , user_id , event_name ,event_time):
        if not await self.event_exists(user_id , event_name):
            return "not found"
        query = """
        DELETE FROM events
        WHERE (user_id) = $1 AND (event_name) = $2 AND (event_time) = $3
        """
        await self.conn.execute(query , user_id , event_name , event_time)
        print(f"deleted {event_name} successfully")
        return "deleted"

    async def update_event(self , user_id , event_name , event_time):
        if not await self.event_exists(user_id , event_name):
            result = "This event doesn't exist in your Schedule"
            return result
        
        query = """
        UPDATE events
        SET event_time = $3
        WHERE user_id = $1 AND event_name = $2
        """

        await self.conn.execute(query , user_id , event_name , event_time)
        return f"Updated \"{event_name}\" event in your Schedule"


class Bot:
    def __init__(self):
        self.BOT_API = "8576466503:AAFGv9L4TSe2iiMWsIX7treumtCW_s99NKI"
        self.app = ApplicationBuilder().token(self.BOT_API).build()
        self.db = DataBase()

    async def start(self , update : Update , context : ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.message.reply_text(text="Welcome! What can I do for you")  
        await self.db.insert_users(user.id , user.username)
        print(f"{update.effective_user.username} started the bot!")

    async def add(self , update : Update , context : ContextTypes.DEFAULT_TYPE):

        if not context.args:
            await update.message.reply_text("Usage: /add <event name> - <event_date(day/month/year)>")
            return

        full_text = ' '.join(context.args)
        print(full_text)

        if " - " not in full_text:
            await update.message.reply_text("Please separate event and date with:  -  (space dash space)")
            return

        event_name , event_time_str = full_text.split(' - ' , 1)

        event_name = event_name.strip()
        event_time_str = event_time_str.strip()

        try:
            event_time = datetime.strptime(event_time_str, "%d/%m/%Y")
            # → datetime(2025, 12, 25, 0, 0)
            print(event_time)
        except ValueError:
            # Wrong format → tell user
            await update.message.reply_text("Wrong date format! Use: DD/MM/YYYY (e.g. 25/12/2025)")
            return

        user = update.effective_user

        await self.db.insert_users(user.id , user.username)

        event_status = await self.db.insert_events(user.id , event_name)

        if event_status == "exists":
            await update.effective_chat.send_message(text=f"Event is already in your Schedule")
        else:
            await update.effective_chat.send_message(text=f"\"{event_name}\" Added to your events Schedule")

    async def remove(self , update : Update , context : ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /remove <event name> - <event_date(day/month/year)>")
            return
        
        full_text = ' '.join(context.args)
        user = update.effective_user
        event_name , event_time_str = full_text.split(' - ' , 1)
        event_name = event_name.strip()
        event_time_str = event_time_str.strip()
        try:
            event_time = datetime.strptime(event_time_str , "%d/%m/%Y")
        except ValueError:
            await update.message.reply_text("Wrong date format! Use: DD/MM/YYYY (e.g. 25/12/2025)")
            return

        status = await self.db.remove_event(user.id , event_name , event_time)
        if status == "not found":
            await update.message.reply_text("Event doesn't exists in your Schedule")
        else :
            await update.message.reply_text(f"Removed {event_name} from your Schedule")

    async def update(self , update : Update , context : ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not context.args:
            await update.message.reply_text("Usage: /update <event name> - <event_date(day/month/year)>")
            return
        
        full_text = ' '.join(context.args)
        print(full_text)

        if " - " not in full_text:
            await update.message.reply_text("Please separate event and date with:  -  (space dash space)")
            return

        event_name , event_time_str = full_text.split(' - ' , 1)

        event_name = event_name.strip()
        event_time_str = event_time_str.strip()

        try:
            event_time = datetime.strptime(event_time_str, "%d/%m/%Y")
            # → datetime(2025, 12, 25, 0, 0)
            print(event_time)
        except ValueError:
            # Wrong format → tell user
            await update.message.reply_text("Wrong date format! Use: DD/MM/YYYY (e.g. 25/12/2025)")
            return

        result = await self.db.update_event(user.id , event_name , event_time)
        await update.message.reply_text(result)


    async def show_events(self , update : Update , context : ContextTypes.DEFAULT_TYPE):
        events = await self.db.show_user_events(update.effective_user.id)
        await update.effective_chat.send_message(text=events)
        print(f"Showed {update.effective_user.username} events")

    async def convert_to_shamsi(self , update : Update , context : ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /convert <event_date>(day/month/year)>")
            return

        full_text = context.args[0]

        try:
            g_dt = datetime.strptime(full_text , "%d/%m/%Y")
            g_date = g_dt.date()
            j_date = jdatetime.date.fromgregorian(date=g_date)

            shamsi = j_date.strftime("%d/%m/%Y")
            await update.message.reply_text(f"Shamsi: {shamsi}")
            print(f"converted {full_text} to {shamsi} for {update.effective_user.username}")

        except ValueError:
            await update.message.reply_text("Invalid date! Use format DD/MM/YYYY\nExample: /convert_to_shamsi 20/12/2025")

    async def convert_to_miladi(self , update : Update , context : ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /convert <event_date>(day/month/year)>")
            return

        full_text = context.args[0]

        try:
            j_dt = jdatetime.datetime.strptime(full_text , "%d/%m/%Y")
            j_date = j_dt.date()
            g_date = j_date.togregorian()

            miladi = g_date.strftime("%d/%m/%Y")
            await update.message.reply_text(f"Miladi: {miladi}")
            print(f"converted {full_text} to {miladi} for {update.effective_user.username}")

        except ValueError:
            await update.message.reply_text("Invalid date! Use format DD/MM/YYYY\nExample: /convert_to_miladi 20/12/2025")

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start" , self.start))
        self.app.add_handler(CommandHandler('add' , self.add))
        self.app.add_handler(CommandHandler('events' , self.show_events))
        self.app.add_handler(CommandHandler('remove' , self.remove))
        self.app.add_handler(CommandHandler('update' , self.update))
        self.app.add_handler(CommandHandler('convert_to_miladi' , self.convert_to_miladi))
        self.app.add_handler(CommandHandler('convert_to_shamsi' , self.convert_to_shamsi))

    async def startup(self , app : Application):
        await self.db.run()

    def run(self):

        self._setup_handlers()
        self.app.job_queue.run_once(self.startup , 0)




        print("Bot is running...")
        self.app.run_polling()
        print("Bot is Closing...")



def main():
    bot = Bot()
    bot.run()



if __name__ == "__main__":
    main()

