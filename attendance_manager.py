import os
from datetime import datetime
import pandas as pd

class AttendanceManager:
    def __init__(self, filename='Attendance.csv'):
        self.filename = filename
        self._initialize_csv()

    def _initialize_csv(self):
        """Creates the CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.filename):
            df = pd.DataFrame(columns=['User_ID', 'Name', 'Department', 'Date', 'Time'])
            df.to_csv(self.filename, index=False)

    def log_attendance(self, user_id, name, department):
        """Logs attendance for a person if not already logged today.
        
        Returns:
            (is_new_log, log_time)
        """
        now = datetime.now()
        date_string = now.strftime('%Y-%m-%d')
        time_string = now.strftime('%H:%M:%S')

        df = pd.read_csv(self.filename)
        
        # Ensure ID columns are treated as strings
        df['User_ID'] = df['User_ID'].astype(str)
        
        # Check if already logged today
        already_logged = df[(df['User_ID'] == str(user_id)) & (df['Date'] == date_string)]
        
        if already_logged.empty:
            new_entry = {
                'User_ID': str(user_id),
                'Name': name,
                'Department': department,
                'Date': date_string,
                'Time': time_string
            }
            df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
            df.to_csv(self.filename, index=False)
            print(f"Attendance logged for {name} ({user_id}) at {time_string}")
            return True, time_string
        else:
            existing_time = already_logged.iloc[0]['Time']
            return False, existing_time

    def get_daily_stats(self, registered_users_dict):
        """Calculates today's attendance stats compared to registered users."""
        if not os.path.exists(self.filename):
            self._initialize_csv()
            
        df = pd.read_csv(self.filename)
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        today_df = df[df['Date'] == today_str]
        unique_present_today = today_df['User_ID'].nunique()
        
        total_registered = len(registered_users_dict)
        absent = max(0, total_registered - unique_present_today)
        
        rate = (unique_present_today / total_registered * 100) if total_registered > 0 else 0.0
        
        return {
            "total_registered": total_registered,
            "present_today": unique_present_today,
            "absent_today": absent,
            "rate": round(rate, 1)
        }

    def get_recent_logs(self, limit=10):
        """Returns the last limit logs."""
        if not os.path.exists(self.filename):
            return []
        try:
            df = pd.read_csv(self.filename)
            # Get last limit rows and reverse to show newest first
            recent = df.tail(limit).iloc[::-1]
            return recent.to_dict(orient='records')
        except Exception as e:
            print(f"Error reading recent logs: {e}")
            return []

    def get_filtered_logs(self, name=None, date_from=None, date_to=None, department=None):
        """Returns filtered logs based on queries."""
        if not os.path.exists(self.filename):
            return []
        try:
            df = pd.read_csv(self.filename)
            df['User_ID'] = df['User_ID'].astype(str)
            
            if name:
                df = df[df['Name'].str.contains(name, case=False, na=False) | df['User_ID'].str.contains(name, case=False, na=False)]
            if department:
                df = df[df['Department'].str.contains(department, case=False, na=False)]
            if date_from:
                df = df[df['Date'] >= date_from]
            if date_to:
                df = df[df['Date'] <= date_to]
                
            # Sort newest logs first
            df = df.sort_values(by=['Date', 'Time'], ascending=False)
            return df.to_dict(orient='records')
        except Exception as e:
            print(f"Error reading filtered logs: {e}")
            return []

    def get_last_7_days_stats(self):
        """Generates last 7 days of attendance counts for trends."""
        if not os.path.exists(self.filename):
            return {"labels": [], "data": []}
        try:
            df = pd.read_csv(self.filename)
            if df.empty:
                return {"labels": [], "data": []}
            
            # Group by Date, count unique User_ID checkins
            daily_counts = df.groupby('Date')['User_ID'].nunique().reset_index()
            # Sort by date and take the last 7 days
            daily_counts = daily_counts.sort_values('Date').tail(7)
            
            return {
                "labels": daily_counts['Date'].tolist(),
                "data": daily_counts['User_ID'].tolist()
            }
        except Exception as e:
            print(f"Error compiling trend data: {e}")
            return {"labels": [], "data": []}

if __name__ == "__main__":
    # Quick test
    manager = AttendanceManager('test_attendance.csv')
    manager.log_attendance('101', 'Test User', 'HR')
    print("Test log completed.")
    print("Recent logs:", manager.get_recent_logs())
    if os.path.exists('test_attendance.csv'):
        os.remove('test_attendance.csv')
