# REST API Concepts & Common Misconceptions Curriculum

## 1. HTTP Verbs and Their Intended Purpose

### GET
- **Purpose**: Retrieve representations of resources from the server.
- **Safety and Idempotency**: Safe (does not modify server state) and idempotent (making multiple identical requests produces the exact same server state).
- **Request Body**: Typically does not include an entity body. Query parameters are passed in the URL.

### POST
- **Purpose**: Submit data to create a new subordinate resource or trigger a server-side processing operation.
- **Safety and Idempotency**: Neither safe nor idempotent. Making two identical POST requests creates two distinct resources or performs the action twice.
- **Request Body**: Contains the data/payload to be processed and stored.

### PUT & PATCH
- **PUT**: Replaces the entire target resource with the uploaded representation (idempotent).
- **PATCH**: Applies partial modifications to a resource.

### DELETE
- **Purpose**: Deletes the specified resource (idempotent).

## 2. Common Misconception: POST vs GET
A frequent beginner misconception is assuming that POST is used to retrieve data from a database because it can carry a JSON body.
- **The Truth**: POST is designed to submit or mutate data, whereas GET is designed to read or fetch data. Using POST solely to read data violates HTTP semantic contracts, disables HTTP caching, and prevents safe retries.

## 3. HTTP Status Code Guidelines
- **200 OK**: Request succeeded and resource representation is returned.
- **201 Created**: Resource created successfully as a result of a POST request.
- **400 Bad Request**: Malformed client payload or validation error.
- **404 Not Found**: Target resource does not exist.
- **500 Internal Server Error**: Unhandled server-side failure.
