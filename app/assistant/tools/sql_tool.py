from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import re


from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class SQLQueryTool:
    """
    Tool class for validating and executing SQL SELECT queries against a predefined database schema.
    """
    ALLOWED_KEYWORDS = [
        "SELECT",
        "FROM",
        "WHERE",
        "JOIN",
        "LEFT JOIN",
        "INNER JOIN",
        "ON",
        "AND",
        "OR",
        "ORDER BY",
        "LIMIT",
        "AS",
        "GROUP BY",
        "HAVING",
        "COUNT",
        "SUM",
        "AVG",
        "MAX",
        "MIN",
        "DISTINCT",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "LIKE",
        "IN",
        "BETWEEN",
        "IS",
        "NULL",
        "NOT",
        "ASC",
        "DESC",
        "CAST",
    ]

    FORBIDDEN_KEYWORDS = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "CALL",
        "MERGE",
        "REPLACE",
    ]

    ALLOWED_TABLES = [
        "bookings",
        "booking_freezes",
        "payments",
        "cars",
        "car_models",
        "locations",
        "status",
        "reviews",
        "users",
        "categories",
        "fuels",
        "capacities",
        "colors",
        "features",
    ]


    def __init__(self):
        self.max_results = 10


    def validate_query(self, query: str) -> Dict[str, Any]:
        """
        Validate the given SQL query to ensure it is a safe SELECT statement
        
        Args:
            query (str): The SQL query string to validate.
        
        Returns:
            Dict[str, Any]: A dictionary with 'valid' (bool) and 'error'
        """
        query_upper = query.upper()

        if not query_upper.strip().startswith("SELECT"):
            return {"valid": False, "error": "Only SELECT queries are allowed"}

        for keyword in self.FORBIDDEN_KEYWORDS:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, query_upper):
                return {
                    "valid": False,
                    "error": f"Forbidden operation detected: {keyword}",
                }

        for keyword in ["--", "/*", "*/", ";", "UNION"]:
            if keyword in query_upper:
                return {
                    "valid": False,
                    "error": f"Potentially unsafe pattern detected: {keyword}",
                }

        found_table = False
        for table in self.ALLOWED_TABLES:
            if table.upper() in query_upper:
                found_table = True
                break

        if not found_table:
            return {
                "valid": False,
                "error": f"Query must reference at least one allowed table: {', '.join(self.ALLOWED_TABLES)}",
            }

        return {"valid": True}


    async def execute_query(
        self,
        db: AsyncSession,
        query: str,
    ) -> Dict[str, Any]:
        """
        Execute the validated SQL query and return results
        
        Args:
            db (AsyncSession): The database session to use for executing the query.
            query (str): The SQL query string to execute.

        Returns:
            Dict[str, Any]: A dictionary with 'success' (bool), 'results' (list), and 'error' (str, optional).
        """
        try:
            query = query.rstrip().rstrip(";")

            validation = self.validate_query(query)
            if not validation["valid"]:
                logger.warning(f"Invalid query attempt: {validation['error']}")
                return {"success": False, "error": validation["error"], "results": []}

            if "LIMIT" not in query.upper():
                query = f"{query.rstrip(';')} LIMIT {self.max_results}"

            # logger.info(f"Executing query for user {user_id}: {query[:200]}")

            result = await db.execute(text(query))
            rows = result.fetchall()

            if not rows:
                return {
                    "success": True,
                    "results": [],
                    "count": 0,
                    "message": "No results found",
                }

            columns = result.keys()
            results = []
            for row in rows:
                row_dict = {}
                for idx, col in enumerate(columns):
                    value = row[idx]
                    if hasattr(value, "isoformat"):
                        row_dict[col] = value.isoformat()
                    elif isinstance(value, (int, float, str, bool, type(None))):
                        row_dict[col] = value
                    else:
                        row_dict[col] = str(value)
                results.append(row_dict)

            return {
                "success": True,
                "results": results,
                "count": len(results),
                "columns": list(columns),
            }

        except Exception as e:
            logger.error(f"Query execution error: {str(e)}")
            return {
                "success": False,
                "error": f"Query execution failed: {str(e)}",
                "results": [],
            }


    def get_schema_info(self) -> str:
        """
        Return a string representation of the database schema for booking queries.
        
        Args:
            None

        Returns:
            str: A detailed description of the database schema including tables, columns, and relationships.
        """
        return """
# Database Schema for Booking Queries

## Available Tables

### bookings
- id: INTEGER (Primary Key)
- car_id: INTEGER (Foreign Key -> cars.id)
- booked_by: STRING (Foreign Key -> users.id)
- start_date: TIMESTAMP WITH TIMEZONE
- end_date: TIMESTAMP WITH TIMEZONE
- delivery_id: INTEGER (Foreign Key -> locations.id)
- pickup_id: INTEGER (Foreign Key -> locations.id)
- booking_status_id: INTEGER (Foreign Key -> status.id)
- payment_status_id: INTEGER (Foreign Key -> status.id, nullable)
- payment_summary: JSONB (contains all charges breakdown)
- remarks: STRING (nullable)
- referral_benefit: BOOLEAN
- start_kilometers: INTEGER (nullable)
- end_kilometers: INTEGER (nullable)
- return_requested_at: TIMESTAMP (nullable)
- cancelled_at: TIMESTAMP (nullable)
- cancellation_reason: STRING (nullable)
- created_at: TIMESTAMP WITH TIMEZONE
- updated_at: TIMESTAMP WITH TIMEZONE

### booking_freezes
- id: INTEGER (Primary Key)
- car_id: INTEGER (Foreign Key -> cars.id)
- user_id: STRING (Foreign Key -> users.id)
- start_date: TIMESTAMP WITH TIMEZONE
- end_date: TIMESTAMP WITH TIMEZONE
- freeze_expires_at: TIMESTAMP WITH TIMEZONE
- is_active: BOOLEAN
- delivery_latitude: FLOAT
- delivery_longitude: FLOAT
- pickup_latitude: FLOAT
- pickup_longitude: FLOAT
- created_at: TIMESTAMP WITH TIMEZONE
- updated_at: TIMESTAMP WITH TIMEZONE

### payments
- id: INTEGER (Primary Key)
- booking_id: INTEGER (Foreign Key -> bookings.id)
- amount_inr: NUMERIC(10,2)
- payment_method: ENUM ('razorpay', 'cash', 'card', etc.)
- payment_type: ENUM ('booking', 'extra_charges', 'refund', etc.)
- status_id: INTEGER (Foreign Key -> status.id)
- transaction_id: STRING (unique)
- razorpay_order_id: STRING (unique)
- razorpay_payment_id: STRING (unique)
- remarks: STRING (nullable)
- created_at: TIMESTAMP WITH TIMEZONE
- updated_at: TIMESTAMP WITH TIMEZONE

### cars
- id: INTEGER (Primary Key)
- car_no: STRING (unique, registration number)
- car_model_id: INTEGER (Foreign Key -> car_models.id)
- color_id: INTEGER (Foreign Key -> colors.id)
- status_id: INTEGER (Foreign Key -> status.id)
- manufacture_year: INTEGER
- created_at: TIMESTAMP WITH TIMEZONE
- updated_at: TIMESTAMP WITH TIMEZONE

### car_models
- id: INTEGER (Primary Key)
- brand: STRING
- model: STRING
- category_id: INTEGER (Foreign Key -> categories.id)
- fuel_id: INTEGER (Foreign Key -> fuels.id)
- capacity_id: INTEGER (Foreign Key -> capacities.id)
- transmission_type: ENUM ('manual', 'automatic')
- mileage: INTEGER
- rental_per_hr: NUMERIC(10,2)
- dynamic_rental_price: NUMERIC(10,2)
- kilometer_limit_per_hr: INTEGER (default 50)
- created_at: TIMESTAMP WITH TIMEZONE
- updated_at: TIMESTAMP WITH TIMEZONE

### locations
- id: INTEGER (Primary Key)
- longitude: FLOAT
- latitude: FLOAT
- address: STRING (nullable, max 500 chars)

### status
- id: INTEGER (Primary Key)
- name: ENUM ('ACTIVE', 'INACTIVE', 'PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED', etc.)

### categories
- id: INTEGER (Primary Key)
- category_name: STRING (unique, e.g., 'SUV', 'Sedan', 'Hatchback')

### fuels
- id: INTEGER (Primary Key)
- fuel_name: STRING (unique, e.g., 'Petrol', 'Diesel', 'Electric', 'Hybrid')

### capacities
- id: INTEGER (Primary Key)
- capacity_value: INTEGER (unique, seating capacity like 5, 7)

### colors
- id: INTEGER (Primary Key)
- color_name: STRING (unique)

### reviews
- id: INTEGER (Primary Key)
- booking_id: INTEGER (Foreign Key -> bookings.id, unique)
- car_id: INTEGER (Foreign Key -> cars.id)
- rating: INTEGER (1-5)
- remarks: TEXT (nullable)
- created_at: TIMESTAMP WITH TIMEZONE
- updated_at: TIMESTAMP WITH TIMEZONE

## Query Guidelines

1. Always filter by user_id when querying user-specific data
2. Use proper JOINs to get related data (use LEFT JOIN for nullable foreign keys)
3. Order results by created_at DESC for chronological listing
4. Limit results to 15 records max
5. Use table aliases for readability (e.g., b for bookings, c for cars)
6. When joining status table multiple times, use different aliases (s_booking, s_payment, etc.)

## Common JOIN Patterns

### Bookings with Complete Car Info:
```sql
FROM bookings b
JOIN cars c ON b.car_id = c.id
JOIN car_models cm ON c.car_model_id = cm.id
LEFT JOIN colors col ON c.color_id = col.id
LEFT JOIN categories cat ON cm.category_id = cat.id
LEFT JOIN fuels f ON cm.fuel_id = f.id
LEFT JOIN capacities cap ON cm.capacity_id = cap.id
```

### Bookings with Status Names:
```sql
JOIN status s_booking ON b.booking_status_id = s_booking.id
LEFT JOIN status s_payment ON b.payment_status_id = s_payment.id
```

### Bookings with Location Details:
```sql
LEFT JOIN locations dl ON b.delivery_id = dl.id
LEFT JOIN locations pl ON b.pickup_id = pl.id
```

### Payments through Bookings:
```sql
FROM payments p
JOIN bookings b ON p.booking_id = b.id
JOIN status s ON p.status_id = s.id
```

## Example Queries

### Booking History (Complete):
```sql
SELECT 
    b.id, b.start_date, b.end_date,
    cm.brand, cm.model, col.color_name,
    cm.transmission_type, f.fuel_name, cap.capacity_value,
    cat.category_name,
    s_booking.name AS booking_status,
    s_payment.name AS payment_status,
    b.payment_summary,
    dl.address AS delivery_address,
    pl.address AS pickup_address,
    b.referral_benefit,
    b.created_at
FROM bookings b
JOIN cars c ON b.car_id = c.id
JOIN car_models cm ON c.car_model_id = cm.id
LEFT JOIN colors col ON c.color_id = col.id
LEFT JOIN categories cat ON cm.category_id = cat.id
LEFT JOIN fuels f ON cm.fuel_id = f.id
LEFT JOIN capacities cap ON cm.capacity_id = cap.id
JOIN status s_booking ON b.booking_status_id = s_booking.id
LEFT JOIN status s_payment ON b.payment_status_id = s_payment.id
LEFT JOIN locations dl ON b.delivery_id = dl.id
LEFT JOIN locations pl ON b.pickup_id = pl.id
WHERE b.booked_by = 'USER_ID_HERE'
ORDER BY b.created_at DESC
LIMIT 15
```

### Payment History (Complete):
```sql
SELECT 
    p.id, p.amount_inr, p.payment_method, p.payment_type,
    p.transaction_id, p.razorpay_order_id, p.razorpay_payment_id,
    s.name AS payment_status,
    b.id AS booking_id, b.start_date, b.end_date,
    cm.brand, cm.model,
    p.created_at
FROM payments p
JOIN status s ON p.status_id = s.id
JOIN bookings b ON p.booking_id = b.id
JOIN cars c ON b.car_id = c.id
JOIN car_models cm ON c.car_model_id = cm.id
WHERE b.booked_by = 'USER_ID_HERE'
ORDER BY p.created_at DESC
LIMIT 15
```

### Freeze History (Complete):
```sql
SELECT 
    bf.id, bf.start_date, bf.end_date,
    bf.freeze_expires_at, bf.is_active,
    bf.delivery_latitude, bf.delivery_longitude,
    bf.pickup_latitude, bf.pickup_longitude,
    cm.brand, cm.model, col.color_name,
    cat.category_name,
    bf.created_at
FROM booking_freezes bf
JOIN cars c ON bf.car_id = c.id
JOIN car_models cm ON c.car_model_id = cm.id
LEFT JOIN colors col ON c.color_id = col.id
LEFT JOIN categories cat ON cm.category_id = cat.id
WHERE bf.user_id = 'USER_ID_HERE'
ORDER BY bf.created_at DESC
LIMIT 15
```
"""


sql_query_tool = SQLQueryTool()
