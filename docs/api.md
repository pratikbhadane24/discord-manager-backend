# API Documentation

This document provides detailed information about the API endpoints available in the T-Backend-Python microservice.

## Base URL

```
http://localhost:8000/api
```

## Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

Alternatively, set the token as a cookie:

```
Cookie: access_token=<your-jwt-token>
```

## Standard Response Format

All API responses follow this standard format:

```json
{
  "success": true,
  "message": "Operation successful",
  "data": { ... }
}
```

## Endpoints

### Health Check Endpoints

#### GET /api/health

Check service health status.

**Authentication:** Not required

**Response:**
```json
{
  "success": true,
  "message": "Service is healthy",
  "data": {
    "service": "T-Backend-Python",
    "version": "1.0.0",
    "status": "ok"
  }
}
```

#### GET /api/health/ready

Check if service is ready to accept requests.

**Authentication:** Not required

**Response:**
```json
{
  "success": true,
  "message": "Service is ready",
  "data": {
    "service": "T-Backend-Python",
    "status": "ready"
  }
}
```

#### GET /api/health/live

Check if service is alive.

**Authentication:** Not required

**Response:**
```json
{
  "success": true,
  "message": "Service is alive",
  "data": {
    "service": "T-Backend-Python",
    "status": "alive"
  }
}
```

### Example Items Endpoints

#### GET /api/examples

List all example items with pagination.

**Authentication:** Required

**Query Parameters:**
- `skip` (integer, default: 0): Number of items to skip
- `limit` (integer, default: 10): Maximum number of items to return

**Response:**
```json
{
  "success": true,
  "message": "Items retrieved successfully",
  "data": [
    {
      "id": 1,
      "name": "Example Item",
      "description": "Item description",
      "is_active": true
    }
  ]
}
```

#### GET /api/examples/{item_id}

Get a specific example item by ID.

**Authentication:** Required

**Path Parameters:**
- `item_id` (integer): ID of the item to retrieve

**Response:**
```json
{
  "success": true,
  "message": "Item retrieved successfully",
  "data": {
    "id": 1,
    "name": "Example Item",
    "description": "Item description",
    "is_active": true
  }
}
```

**Error Response (404):**
```json
{
  "detail": "Item with id 1 not found"
}
```

#### POST /api/examples

Create a new example item.

**Authentication:** Required

**Request Body:**
```json
{
  "name": "New Item",
  "description": "Item description",
  "is_active": true
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Item created successfully",
  "data": {
    "id": 1,
    "name": "New Item",
    "description": "Item description",
    "is_active": true
  }
}
```

#### PUT /api/examples/{item_id}

Update an existing example item.

**Authentication:** Required

**Path Parameters:**
- `item_id` (integer): ID of the item to update

**Request Body:**
```json
{
  "name": "Updated Item",
  "description": "Updated description",
  "is_active": false
}
```

All fields are optional. Only provided fields will be updated.

**Response:**
```json
{
  "success": true,
  "message": "Item updated successfully",
  "data": {
    "id": 1,
    "name": "Updated Item",
    "description": "Updated description",
    "is_active": false
  }
}
```

#### DELETE /api/examples/{item_id}

Delete an example item.

**Authentication:** Required

**Path Parameters:**
- `item_id` (integer): ID of the item to delete

**Response:**
```json
{
  "success": true,
  "message": "Item deleted successfully",
  "data": null
}
```

## Error Responses

### 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

### 404 Not Found

```json
{
  "detail": "Item with id X not found"
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Interactive Documentation

For interactive API exploration and testing, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing with cURL

### Health Check

```bash
curl http://localhost:8000/api/health
```

### Create Token (Example)

```bash
# In production, you would have a login endpoint that returns a token
# For testing, you can generate a token using Python:
python -c "from app.core.security import create_access_token; print(create_access_token({'sub': 'user123'}))"
```

### List Items

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/examples
```

### Create Item

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Item", "description": "Test"}' \
  http://localhost:8000/api/examples
```

### Get Item

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/examples/1
```

### Update Item

```bash
curl -X PUT \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Item"}' \
  http://localhost:8000/api/examples/1
```

### Delete Item

```bash
curl -X DELETE \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/examples/1
```
