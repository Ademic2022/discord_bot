from discord.ext import commands, tasks
from datetime import datetime, timedelta
import logging
from config import Config
from utils.db_manager import DatabaseManager

class PunctualityTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()
        self.logger = logging.getLogger('discord_bot')
        self.active_meetings = {}  # channel_id -> meeting_id
        self.scheduled_meetings = {}  # channel_id -> (meeting_id, scheduled_meeting_datetime, description)
        self.tracked_users = set()  # Set of user_ids who have been tracked for the current meeting
        self.check_scheduled_meetings.start()
    
    def cog_unload(self):
        self.check_scheduled_meetings.cancel()
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Skip bot updates
        if member.bot:
            return
        
        meeting_channel_id = Config.MEETING_CHANNEL_ID
        
        # Only care about joining the meeting channel
        if after.channel and after.channel.id == meeting_channel_id:
            # Skip if this user has already been tracked for the current meeting
            if member.id in self.tracked_users:
                return
                
            await self.handle_join(member, after.channel)
    
    async def handle_join(self, member, voice_channel):
        """Handle a member joining the meeting channel"""
        now = datetime.now()
        channel_id = voice_channel.id
        today = now.strftime("%Y-%m-%d")
        
        # Check if there's an active meeting for this channel today
        meeting = self.db.get_active_meeting(channel_id, today)
        
        if not meeting:
            # No active meeting, we won't track this join
            self.logger.info(f"No active meeting found for channel {channel_id} on {today}")
            return
        
        meeting_id = meeting[0]
        start_time_str = meeting[2]
        
        # Parse the start time
        start_time = datetime.strptime(f"{today} {start_time_str}", "%Y-%m-%d %H:%M:%S")
        
        # Calculate lateness
        time_diff = now - start_time
        late_minutes = max(0, int(time_diff.total_seconds() / 60) - Config.GRACE_PERIOD_MINUTES)
        
        # Calculate fee if late
        fee_amount = 0
        if late_minutes > 0:
            fee_amount = late_minutes * Config.FEE_PER_MINUTE
        
        # Record punctuality
        self.db.record_punctuality(
            meeting_id,
            member.id,
            member.display_name,
            now.strftime("%H:%M:%S"),
            late_minutes,
            fee_amount
        )
        
        # Add to tracked users
        self.tracked_users.add(member.id)
        
        # Get the announcement channel for notifications
        announcement_channel = self.bot.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
        if not announcement_channel:
            self.logger.error(f"Announcement channel {Config.ANNOUNCEMENT_CHANNEL_ID} not found")
            return
            
        # Notify if late
        if late_minutes > 0:
            try:
                await announcement_channel.send(
                    f"⏰ {member.mention} joined {late_minutes} minute(s) late. "
                    f"Fee: ${fee_amount:.2f}"
                )
            except Exception as e:
                self.logger.error(f"Error sending late notification: {e}")
        else:
            try:
                await announcement_channel.send(f"✅ {member.mention} joined on time")
            except Exception as e:
                self.logger.error(f"Error sending on-time notification: {e}")
    
    @commands.command(name="schedule")
    @commands.has_permissions(administrator=True)
    async def schedule_meeting(self, ctx, minutes: str, *, description=None):
        """Schedule a meeting X minutes from now"""
        try:
            # Validate minutes
            try:
                minutes_from_now = int(minutes)
                if minutes_from_now < 1:
                    raise ValueError()
            except ValueError:
                await ctx.send("❌ Please provide a positive number of minutes (e.g. `!schedule 6`)")
                return

            # Calculate meeting time
            now = datetime.now()
            meeting_time = now + timedelta(minutes=minutes_from_now)
            
            # Get meeting voice channel
            voice_channel = self.bot.get_channel(Config.MEETING_CHANNEL_ID)
            if not voice_channel:
                await ctx.send("❌ Error: Meeting voice channel not found!")
                self.logger.error(f"Voice channel {Config.MEETING_CHANNEL_ID} not found")
                return
                
            # Get announcement text channel
            announcement_channel = self.bot.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
            if not announcement_channel:
                await ctx.send("❌ Error: Announcement text channel not found!")
                self.logger.error(f"Announcement channel {Config.ANNOUNCEMENT_CHANNEL_ID} not found")
                return
                
            # Check if there's already a scheduled meeting
            if voice_channel.id in self.scheduled_meetings:
                await ctx.send("❌ There is already a scheduled meeting for this channel. Please cancel it first with `!cancelmeeting`")
                return

            # Create database record
            meeting_id = self.db.create_meeting(
                meeting_date=meeting_time.strftime("%Y-%m-%d"),
                start_time=meeting_time.strftime("%H:%M:%S"),
                channel_id=voice_channel.id,
                description=description
            )

            if not meeting_id:
                await ctx.send("❌ Failed to create meeting record")
                return

            # Store scheduled meeting with its ID
            self.scheduled_meetings[voice_channel.id] = (meeting_id, meeting_time, description)
            
            # Send confirmation to user and announcement to the text channel
            await ctx.send(f"✅ Meeting scheduled to start in {minutes_from_now} minutes")
            try:
                await announcement_channel.send(
                    f"📅 **New meeting scheduled** to start in {minutes_from_now} minutes "
                    f"({meeting_time.strftime('%H:%M')})\n"
                    f"*{description or 'No description provided'}*"
                )
                self.logger.info(f"Meeting scheduled for {meeting_time} in channel {voice_channel.id}")
            except Exception as e:
                self.logger.error(f"Error sending meeting announcement: {e}")
                await ctx.send("⚠️ Scheduled the meeting but couldn't send announcement to the channel")
            
        except Exception as e:
            self.logger.error(f"Schedule error: {str(e)}")
            await ctx.send("❌ Error scheduling meeting")
            
    @commands.command(name="cancelmeeting")
    @commands.has_permissions(administrator=True)
    async def cancel_meeting(self, ctx):
        """Cancel a scheduled meeting"""
        voice_channel_id = Config.MEETING_CHANNEL_ID
        
        if voice_channel_id not in self.scheduled_meetings:
            await ctx.send("❌ No meeting is currently scheduled")
            return
            
        _, meeting_time, description = self.scheduled_meetings[voice_channel_id]
        del self.scheduled_meetings[voice_channel_id]
        
        await ctx.send(f"✅ Scheduled meeting for {meeting_time.strftime('%H:%M')} has been cancelled")
        
        # Notify the announcement channel
        announcement_channel = self.bot.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
        if announcement_channel:
            try:
                await announcement_channel.send(f"🚫 The meeting scheduled for {meeting_time.strftime('%H:%M')} has been cancelled")
            except Exception as e:
                self.logger.error(f"Error sending cancellation notice: {e}")

    @commands.command(name="startmeeting")
    @commands.has_permissions(administrator=True)
    async def start_meeting(self, ctx, *, description=None):
        """Start a meeting immediately for punctuality tracking"""
        now = datetime.now()
        voice_channel_id = Config.MEETING_CHANNEL_ID
        
        # Create meeting record
        meeting_id = self.db.create_meeting(
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            voice_channel_id,
            description
        )
        
        if meeting_id:
            # Clear tracked users for the new meeting
            self.tracked_users.clear()
            
            # Store active meeting
            self.active_meetings[voice_channel_id] = meeting_id
            
            # Cancel any scheduled meeting for this channel
            if voice_channel_id in self.scheduled_meetings:
                del self.scheduled_meetings[voice_channel_id]
            
            # Announce meeting start to the text channel
            announcement_channel = self.bot.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
            if announcement_channel:
                desc_text = f" - {description}" if description else ""
                try:
                    await announcement_channel.send(
                        f"🔔 **MEETING STARTED** at {now.strftime('%H:%M:%S')}{desc_text}\n"
                        f"Grace period: {Config.GRACE_PERIOD_MINUTES} minutes\n"
                        f"Late fee: ₦{Config.FEE_PER_MINUTE:.2f} per minute"
                    )
                except Exception as e:
                    self.logger.error(f"Error announcing meeting start: {e}")
                    await ctx.send("⚠️ Started meeting but couldn't send announcement to the channel")
            
            await ctx.send(f"✅ Meeting started. Punctuality tracking is active.")
            self.logger.info(f"Meeting started at {now} in channel {voice_channel_id}")
        else:
            await ctx.send("❌ Failed to start meeting. Check logs for details.")
    
    @commands.command(name="report")
    @commands.has_permissions(administrator=True)
    async def get_report(self, ctx, date: str = None):
        """Get punctuality report for the specified date or today
        
        Args:
            date: Optional date in YYYY-MM-DD format (defaults to today)
        """
        channel_id = Config.MEETING_CHANNEL_ID
        
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            
            # Get meeting for the date
            meeting = self.db.get_active_meeting(channel_id, date)
            
            if not meeting:
                await ctx.send(f"No meetings found for {date}")
                return
            
            meeting_id = meeting[0]
            meeting_time = meeting[2]
            meeting_desc = meeting[3] or "Regular Meeting"
            
            # Get punctuality report
            records = self.db.get_punctuality_report(meeting_id)
            
            if not records:
                await ctx.send(f"No punctuality records found for meeting on {date}")
                return
            
            # Format report
            report = f"📊 **Punctuality Report - {date} {meeting_time}**\n"
            report += f"**Meeting: {meeting_desc}**\n\n"
            report += "| Name | Join Time | Late (min) | Fee |\n"
            report += "|------|-----------|------------|-----|\n"
            
            total_fees = 0
            for record in records:
                name, join_time, late_min, fee = record
                status = "🔴 LATE" if late_min > 0 else "🟢 ON TIME"
                report += f"| {name} | {join_time} | {late_min} {status} | ${fee:.2f} |\n"
                total_fees += fee
            
            report += f"\n**Total Fees: ${total_fees:.2f}**"
            
            await ctx.send(report)
            
        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            await ctx.send("An error occurred while retrieving the report.")
    
    @commands.command(name="meetings")
    @commands.has_permissions(administrator=True)
    async def list_meetings(self, ctx):
        """List recent meetings"""
        meetings = self.db.get_all_meetings()
        
        if not meetings:
            await ctx.send("No meetings found in the database.")
            return
        
        report = "📅 **Recent Meetings**\n\n"
        report += "| Date | Time | Description |\n"
        report += "|------|------|-------------|\n"
        
        for meeting in meetings:
            meeting_id, date, time, desc = meeting
            description = desc or "Regular Meeting"
            report += f"| {date} | {time} | {description} |\n"
        
        report += f"\nUse `!report YYYY-MM-DD` to get punctuality report for a specific date."
        
        await ctx.send(report)
    
    @tasks.loop(minutes=1)
    async def check_scheduled_meetings(self):
        """Check for upcoming meetings and send reminders"""
        now = datetime.now()
        
        for voice_channel_id, (meeting_id, meeting_time, description) in list(self.scheduled_meetings.items()):
            time_diff = meeting_time - now
            minutes_until_meeting = time_diff.total_seconds() / 60
            
            # Get the announcement channel for sending messages
            announcement_channel = self.bot.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
            if not announcement_channel:
                self.logger.error(f"Announcement channel {Config.ANNOUNCEMENT_CHANNEL_ID} not found")
                continue
                
            # Send reminder at configured time before meeting
            if minutes_until_meeting <= Config.REMINDER_MINUTES and minutes_until_meeting > 0:
                desc_text = f" - {description}" if description else ""
                try:
                    await announcement_channel.send(
                        f"⏰ **REMINDER:** Meeting starts in {int(minutes_until_meeting)} minutes{desc_text}! "
                        f"Please join the voice channel on time to avoid late fees."
                    )
                    self.logger.info(f"Sent reminder for meeting at {meeting_time}")
                except Exception as e:
                    self.logger.error(f"Error sending reminder: {e}")
                
                # Clear tracked users when reminder is sent
                self.tracked_users.clear()
            
            # If meeting time has passed (within 1 minute), announce meeting start
            elif minutes_until_meeting <= 0 and minutes_until_meeting > -2:  # Expanded window to catch meetings
                desc_text = f" - {description}" if description else ""
                try:
                    await announcement_channel.send(
                        f"🔔 **MEETING STARTED** at {meeting_time.strftime('%H:%M:%S')}{desc_text}\n"
                        f"Grace period: {Config.GRACE_PERIOD_MINUTES} minutes\n"
                        f"Late fee: ${Config.FEE_PER_MINUTE:.2f} per minute"
                    )
                    self.logger.info(f"Auto-started meeting at {meeting_time}")
                except Exception as e:
                    self.logger.error(f"Error auto-starting meeting: {e}")
                
                # Store active meeting ID
                self.active_meetings[voice_channel_id] = meeting_id
                
                # Clear tracked users for the new meeting
                self.tracked_users.clear()
                
                # Remove from scheduled meetings
                del self.scheduled_meetings[voice_channel_id]
            
            # Clean up very old scheduled meetings (more than 10 minutes past)
            elif minutes_until_meeting < -10:
                self.logger.warning(f"Removing stale scheduled meeting from {meeting_time}")
                del self.scheduled_meetings[voice_channel_id]
    
    @commands.command(name="shutdown")
    @commands.has_permissions(administrator=True)
    async def shutdown(self, ctx):
        """Shut down the bot"""
        await ctx.send("Shutting down the bot... 👋")
        self.logger.info("Bot is shutting down...")
        await self.bot.close()  # Shut down the bot

    @check_scheduled_meetings.before_loop
    async def before_check_scheduled_meetings(self):
        await self.bot.wait_until_ready()