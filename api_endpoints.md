# Siraj (سراج) — API Endpoint Reference

This document outlines all the endpoints available in the Siraj FastAPI application. You can use these details to configure requests in Postman or integrate with the frontend application.

* **Base URL**: `http://127.0.0.1:8000`
* **Interactive Swagger Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🔒 Authentication Setup in Postman
Most endpoints require authentication. Follow these steps to authorize requests:

1. **Register a User**: Send a `POST` request to `/api/v1/auth/register` (see details below).
2. **Log In**: Send a `POST` request to `/api/v1/auth/login` to retrieve the `access_token`.
3. **Authorize in Postman**: 
   * Copy the `access_token` string from the login response.
   * Go to the **Authorization** tab of your request or collection in Postman.
   * Select **Auth Type**: `Bearer Token`.
   * Paste the token in the **Token** field.

---

## 📋 Endpoint Catalog

### 1. Authentication (`/api/v1/auth`)
| Method | Endpoint | Description | Request Body Example (JSON) |
| :--- | :--- | :--- | :--- |
| **POST** | `http://127.0.0.1:8000/api/v1/auth/register` | Register a new user | `{"email": "sara@siraj.sa", "full_name": "سارة القرني", "password": "password123", "currency": "SAR"}` |
| **POST** | `http://127.0.0.1:8000/api/v1/auth/login` | Login to retrieve Bearer token | `{"email": "sara@siraj.sa", "password": "password123"}` |
| **GET** | `http://127.0.0.1:8000/api/v1/auth/me` | Get profile details of current user | *(Requires Bearer Token)* |

---

### 2. Dashboard (`/api/v1/dashboard`) *(All Require Auth)*
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `http://127.0.0.1:8000/api/v1/dashboard/overview` | Monthly income, expense, savings totals & savings rate. |
| **GET** | `http://127.0.0.1:8000/api/v1/dashboard/category-breakdown` | Expense breakdown by category with amounts and percentages. |
| **GET** | `http://127.0.0.1:8000/api/v1/dashboard/health-score` | Financial Health Score (0-100), Arabic grade, and insights. |
| **GET** | `http://127.0.0.1:8000/api/v1/dashboard/daily-tip` | Generates a daily financial tip in Arabic. |
| **GET** | `http://127.0.0.1:8000/api/v1/dashboard/alerts/active` | Retrieve unread critical budget and spending alerts. |
| **GET** | `http://127.0.0.1:8000/api/v1/dashboard/goals/summary` | Summary of progress across savings and financial goals. |

---

### 3. Transactions (`/api/v1/transactions`) *(All Require Auth)*
| Method | Endpoint | Description | Request Body / Query Parameters |
| :--- | :--- | :--- | :--- |
| **GET** | `http://127.0.0.1:8000/api/v1/transactions/` | List transactions (supports query filters) | **Query Params**: `start_date`, `end_date`, `category`, `type` |
| **POST** | `http://127.0.0.1:8000/api/v1/transactions/` | Create a new transaction | `{"amount": 150.00, "category": "الترفيه والمطاعم", "type": "expense", "description": "شراء عشاء من البيك", "transaction_date": "2026-07-12"}` |
| **DELETE** | `http://127.0.0.1:8000/api/v1/transactions/{id}` | Delete a specific transaction | Replace `{id}` with the UUID of the transaction |

---

### 4. Budgets (`/api/v1/budgets`) *(All Require Auth)*
| Method | Endpoint | Description | Request Body Example (JSON) |
| :--- | :--- | :--- | :--- |
| **GET** | `http://127.0.0.1:8000/api/v1/budgets/` | List all category budgets | *None* |
| **POST** | `http://127.0.0.1:8000/api/v1/budgets/` | Set or update a category budget | `{"category": "الغذاء والبقالة", "limit_amount": 2500.00, "period": "monthly"}` |
| **GET** | `http://127.0.0.1:8000/api/v1/budgets/analysis` | Monthly category limit vs actual spending analysis | *None* |

---

### 5. Savings Plans (`/api/v1/savings`) *(All Require Auth)*
| Method | Endpoint | Description | Request Body Example (JSON) |
| :--- | :--- | :--- | :--- |
| **GET** | `http://127.0.0.1:8000/api/v1/savings/plans` | List active savings plans | *None* |
| **POST** | `http://127.0.0.1:8000/api/v1/savings/plans` | Create a new savings plan | `{"goal_name": "رحلة سياحية", "target_amount": 10000.00, "current_amount": 1000.00, "target_date": "2026-12-31", "monthly_contribution": 1500.00}` |
| **PUT** | `http://127.0.0.1:8000/api/v1/savings/plans/{id}` | Update progress of a plan | `{"current_amount": 2500.00, "status": "active"}` |
| **GET** | `http://127.0.0.1:8000/api/v1/savings/plans/{id}/progress` | Get detailed estimations & track status | *None* (Replace `{id}` with Plan UUID) |

---

### 6. Financing (`/api/v1/financing`) *(All Require Auth)*
| Method | Endpoint | Description | Request Body Example (JSON) |
| :--- | :--- | :--- | :--- |
| **GET** | `http://127.0.0.1:8000/api/v1/financing/products` | Browse available Islamic financing options | *None* |
| **POST** | `http://127.0.0.1:8000/api/v1/financing/requests` | Submit a financing request | `{"product_type": "personal", "amount": 80000.00, "term_months": 24, "notes": "شراء مستلزمات"}` |
| **GET** | `http://127.0.0.1:8000/api/v1/financing/requests` | List user's submitted financing requests | *None* |
| **GET** | `http://127.0.0.1:8000/api/v1/financing/requests/{id}` | Get status timeline of a request | *None* (Replace `{id}` with Request UUID) |

---

### 7. Investment (`/api/v1/investment`) *(All Require Auth)*
| Method | Endpoint | Description | Request Body Example (JSON) |
| :--- | :--- | :--- | :--- |
| **GET** | `http://127.0.0.1:8000/api/v1/investment/opportunities` | List active investment products (Sukuks, funds, IPOs) | *None* |
| **POST** | `http://127.0.0.1:8000/api/v1/investment/requests` | Submit an investment application | `{"product_name": "صكوك الإنماء العقارية المبتكرة", "product_type": "sukuk", "amount": 5000.00, "risk_level": "low", "expected_return": 6.25}` |
| **GET** | `http://127.0.0.1:8000/api/v1/investment/requests` | List user's active investments | *None* |
| **GET** | `http://127.0.0.1:8000/api/v1/investment/recommendations` | Get personalized investment recommendations | *None* |

---

### 8. Financial Goals (`/api/v1/goals`) *(All Require Auth)*
| Method | Endpoint | Description | Request Body Example (JSON) |
| :--- | :--- | :--- | :--- |
| **GET** | `http://127.0.0.1:8000/api/v1/goals/` | List active seasonal & long-term goals | *None* |
| **GET** | `http://127.0.0.1:8000/api/v1/goals/templates` | List pre-built templates (Hajj, Umrah, Ramadan, etc.) | *None* |
| **POST** | `http://127.0.0.1:8000/api/v1/goals/` | Create a new financial goal | `{"goal_type": "umrah", "title": "رحلة العمرة 2027", "target_amount": 6000.00, "saved_amount": 0.0, "target_date": "2027-01-15"}` |
| **PUT** | `http://127.0.0.1:8000/api/v1/goals/{id}` | Update title, target amount, or saved progress | `{"saved_amount": 1500.00}` |
| **POST** | `http://127.0.0.1:8000/api/v1/goals/{id}/plan` | Trigger rule-based AI financial planner for a goal | *None* (Replace `{id}` with Goal UUID) |

---

### 9. Smart Alerts (`/api/v1/alerts`) *(All Require Auth)*
| Method | Endpoint | Description | Request Body Example (JSON) |
| :--- | :--- | :--- | :--- |
| **GET** | `http://127.0.0.1:8000/api/v1/alerts/` | List all historical alerts | *None* |
| **POST** | `http://127.0.0.1:8000/api/v1/alerts/` | Create a custom alert | `{"alert_type": "spending_spike", "category": "التسوق والمستلزمات", "threshold_amount": 1000.00, "message": "تنبيه مصاريف التسوق مرتفعة"}` |
| **PUT** | `http://127.0.0.1:8000/api/v1/alerts/{id}/read` | Mark alert as read | *None* (Replace `{id}` with Alert UUID) |
| **GET** | `http://127.0.0.1:8000/api/v1/alerts/unread-count` | Returns count of active unread alerts | *None* |

---

### 10. AI Chat / Siraj AI (`/api/v1/chat`) *(All Require Auth)*
| Method | Endpoint | Description | Request Body Example (JSON) |
| :--- | :--- | :--- | :--- |
| **POST** | `http://127.0.0.1:8000/api/v1/chat/sessions` | Initialize a new chat session | `{"title": "استفسار عن الادخار"}` |
| **GET** | `http://127.0.0.1:8000/api/v1/chat/sessions` | List user's chat sessions history | *None* |
| **GET** | `http://127.0.0.1:8000/api/v1/chat/sessions/{id}/messages` | Get message history of a chat session | *None* (Replace `{id}` with Session UUID) |
| **POST** | `http://127.0.0.1:8000/api/v1/chat/sessions/{id}/messages` | Send message and receive **SSE Stream** | `{"content": "أبي أقدم على تمويل شخصي"}` |

> [!TIP]
> **Testing SSE in Postman**: When sending a `POST` request to the chat messages streaming endpoint, Postman will automatically detect the `text/event-stream` response header and stream the chunks in the **Response Console** in real time!
