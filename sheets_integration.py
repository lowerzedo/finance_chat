import json
import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import logging

logger = logging.getLogger(__name__)

class SheetsManager:
    def __init__(self, credentials_json=None, spreadsheet_id=None):
        """Initialize Google Sheets connection"""
        self.spreadsheet_id = spreadsheet_id or os.environ.get('GOOGLE_SHEETS_ID')
        
        # Setup credentials
        if credentials_json:
            creds_dict = json.loads(credentials_json)
            self.credentials = Credentials.from_service_account_info(
                creds_dict, 
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
        else:
            # For local development - use service account file
            self.credentials = Credentials.from_service_account_file(
                'service_account.json',
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
        
        self.service = build('sheets', 'v4', credentials=self.credentials)
        self.sheet = self.service.spreadsheets()
    
    def setup_sheets(self):
        """Create the required sheets if they don't exist"""
        try:
            # Get existing sheets
            result = self.sheet.get(spreadsheetId=self.spreadsheet_id).execute()
            existing_sheets = [s['properties']['title'] for s in result['sheets']]
            
            requests = []
            
            # Create Expenses sheet
            if 'Expenses' not in existing_sheets:
                requests.append({
                    'addSheet': {
                        'properties': {
                            'title': 'Expenses'
                        }
                    }
                })
            
            # Create Monthly_Totals sheet  
            if 'Monthly_Totals' not in existing_sheets:
                requests.append({
                    'addSheet': {
                        'properties': {
                            'title': 'Monthly_Totals'
                        }
                    }
                })
            
            if requests:
                self.sheet.batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': requests}
                ).execute()
            
            # Setup headers
            self._setup_headers()
            
        except Exception as e:
            logger.error(f"Error setting up sheets: {e}")
            return False
        
        return True
    
    def _setup_headers(self):
        """Setup headers for both sheets"""
        try:
            # Expenses sheet headers
            expense_headers = [['Date', 'Amount', 'Category', 'Description', 'Merchant', 'Month']]
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Expenses!A1:F1',
                valueInputOption='RAW',
                body={'values': expense_headers}
            ).execute()
            
            # Monthly totals headers
            monthly_headers = [['Month', 'Total_Amount', 'Food', 'Transport', 'Utilities', 'Shopping', 'Entertainment', 'Healthcare', 'Other']]
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Monthly_Totals!A1:I1',
                valueInputOption='RAW',
                body={'values': monthly_headers}
            ).execute()
            
        except Exception as e:
            logger.error(f"Error setting up headers: {e}")
    
    def log_expense(self, expense_data):
        """Log a single expense to the Expenses sheet"""
        try:
            date_str = expense_data.get('date', datetime.now().strftime('%Y-%m-%d'))
            month_str = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m')
            
            row_data = [
                date_str,
                expense_data.get('amount', 0),
                expense_data.get('category', 'other'),
                expense_data.get('description', ''),
                expense_data.get('merchant', ''),
                month_str
            ]
            
            # Append to expenses sheet
            self.sheet.values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Expenses!A:F',
                valueInputOption='USER_ENTERED',
                body={'values': [row_data]}
            ).execute()
            
            # Update monthly totals
            self._update_monthly_totals(month_str)
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging expense: {e}")
            return False
    
    def _update_monthly_totals(self, month_str):
        """Update or create monthly totals for the given month"""
        try:
            # Get current monthly totals
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Monthly_Totals!A:I'
            ).execute()
            
            values = result.get('values', [])
            
            # Find if month exists
            month_row = None
            for i, row in enumerate(values[1:], 2):  # Skip header
                if row and row[0] == month_str:
                    month_row = i
                    break
            
            # Calculate totals for this month
            expense_result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Expenses!A:F'
            ).execute()
            
            expense_values = expense_result.get('values', [])
            
            # Calculate category totals
            totals = {
                'total': 0,
                'food': 0,
                'transport': 0,
                'utilities': 0,
                'shopping': 0,
                'entertainment': 0,
                'healthcare': 0,
                'other': 0
            }
            
            for row in expense_values[1:]:  # Skip header
                if len(row) >= 6 and row[5] == month_str:  # Month column
                    amount = float(row[1]) if row[1] else 0
                    category = row[2].lower() if row[2] else 'other'
                    
                    totals['total'] += amount
                    if category in totals:
                        totals[category] += amount
                    else:
                        totals['other'] += amount
            
            # Update or insert row
            new_row = [
                month_str,
                totals['total'],
                totals['food'],
                totals['transport'],
                totals['utilities'],
                totals['shopping'],
                totals['entertainment'],
                totals['healthcare'],
                totals['other']
            ]
            
            if month_row:
                # Update existing row
                self.sheet.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'Monthly_Totals!A{month_row}:I{month_row}',
                    valueInputOption='USER_ENTERED',
                    body={'values': [new_row]}
                ).execute()
            else:
                # Append new row
                self.sheet.values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range='Monthly_Totals!A:I',
                    valueInputOption='USER_ENTERED',
                    body={'values': [new_row]}
                ).execute()
                
        except Exception as e:
            logger.error(f"Error updating monthly totals: {e}")
    
    def get_monthly_total(self, month_str=None):
        """Get total for current or specified month"""
        if not month_str:
            month_str = datetime.now().strftime('%Y-%m')
        
        try:
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Monthly_Totals!A:I'
            ).execute()
            
            values = result.get('values', [])
            
            for row in values[1:]:  # Skip header
                if row and row[0] == month_str:
                    return {
                        'month': row[0],
                        'total': float(row[1]) if len(row) > 1 and row[1] else 0,
                        'food': float(row[2]) if len(row) > 2 and row[2] else 0,
                        'transport': float(row[3]) if len(row) > 3 and row[3] else 0,
                        'utilities': float(row[4]) if len(row) > 4 and row[4] else 0,
                        'shopping': float(row[5]) if len(row) > 5 and row[5] else 0,
                        'entertainment': float(row[6]) if len(row) > 6 and row[6] else 0,
                        'healthcare': float(row[7]) if len(row) > 7 and row[7] else 0,
                        'other': float(row[8]) if len(row) > 8 and row[8] else 0
                    }
            
            return {'month': month_str, 'total': 0}
            
        except Exception as e:
            logger.error(f"Error getting monthly total: {e}")
            return {'month': month_str, 'total': 0} 