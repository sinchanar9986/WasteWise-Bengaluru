# Waste Wise Bengaluru — Setup

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Create MySQL database

```bash
mysql -u root -p
```

```sql
CREATE DATABASE wastewise;
EXIT;
```

## 3. Run schema and seed

```bash
mysql -u root -p wastewise < data/schema.sql
mysql -u root -p wastewise < data/seed.sql
```

## 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
DB_HOST=localhost
DB_USER=root
DB_PASS=your_password
DB_NAME=wastewise
WATSONX_API_KEY=your_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

> **Note:** If `WATSONX_API_KEY` / `WATSONX_PROJECT_ID` are not set, the system automatically falls
> back to regex-based parsing and template-based explanations — the demo still works fully.

## 5. Run the application

```bash
python app.py
```

Flask starts on port 5000. You should see:
```
 * Running on http://127.0.0.1:5000
```

## 6. Open browser

Navigate to **http://localhost:5000**

The dashboard loads with pre-seeded facility data and 3 historical allocations.
