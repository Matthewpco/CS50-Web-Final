import os

from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Application for web based stock trading built by Matthew Payne as final project for Harvard's most popular course: CS50
# 11/19/2020

# API Key Cmd to enter first in terminal: export API_KEY=pk_f8d15fd6397d44b38fcc6cbb4cd0ad62
# To start the server execute: flask run from finance directory

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("postgres://awibzamtgxvkxk:7398e9c85a95715f51a7a896f9314a98fc3cea5a46906fa84a11494ebd7bb728@ec2-54-163-47-62.compute-1.amazonaws.com:5432/dfbgflglvvg6gj")


@app.route("/")
@login_required
def index():

    """Show portfolio of stocks"""

    # Select stocks from portfolio
    stocks = db.execute("SELECT symbol, shares FROM portfolio WHERE username = :username",
    username=session["username"])

    # Array to hold the combined price of shares
    total_value = []

    # Sort through and assign data from db
    for stock in stocks:
        symbol = stock["symbol"]
        shares = stock["shares"]
        name = lookup(symbol)["name"]
        price = lookup(symbol)["price"]
        total_price = shares * price
        stock["name"] = name
        stock["price"] = usd(price)
        stock["total_price"] = usd(total_price)
        total_value.append(total_price)


    # Get cash
    rows_cash = db.execute("SELECT cash FROM users WHERE username = :username",
    username=session["username"])

    cash_available = rows_cash [0]['cash']

    # Total of cash and sum of shares
    full_value = sum(total_value) + cash_available

    # Round decimal places
    full_round = round(full_value)
    cash_round = round(cash_available, 2)

    # Convert to usd
    full_round = usd(full_round)
    cash_round = usd(cash_round)

    # Redirect with passed values
    return render_template("index.html", stocks=stocks, cash_round=cash_round, full_round=full_round)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get and store form input for easy access
        get_symbol = request.form.get("symbol")
        get_shares = request.form.get("shares")

        # Used for inserting datetime into db
        dt = datetime.now()
        date = dt.strftime("%x")
        time = dt.strftime("%X")

        # Query API to get stock data
        try:
            stock = lookup(get_symbol)['name']
            price = lookup(get_symbol)['price']
            symbol = lookup(get_symbol)['symbol']

        # Error control
        except:
            return apology(" Must provide a stock symbol ")

         # Ensure shares submitted
        if not get_shares or int(get_shares) < 1:
            return apology("must provide positive number of shares", 403)

        # Value of combined shares
        shares_price = price * float(get_shares)

        # Get cash from db
        get_cash = db.execute("SELECT cash FROM users WHERE id = :id",
        id=session["user_id"])

        # Error control - Check cash against price of total shares
        if float(get_cash[0]["cash"]) < shares_price:
            return apology("Sorry not enough Ca$h")

        # Cash left after purchase
        cash_left = float(get_cash[0]["cash"]) - shares_price

        # Register cash in db
        db.execute("UPDATE users SET cash = :cash_left WHERE id = :id",
        cash_left=cash_left, id=session['user_id'])

        # Check if shares already in table
        rows_existing_shares = db.execute("SELECT shares FROM portfolio WHERE username = :username AND symbol = :symbol",
        username=session["username"],
        symbol=symbol)

        # If shares exist in db Update else Insert new values
        if len(rows_existing_shares) != 0:

            # Get current shares and total of new shares
            current_shares = rows_existing_shares[0]['shares']
            new_share_total = float(current_shares) + float(get_shares)

            db.execute("UPDATE portfolio SET shares = :shares WHERE username = :username AND symbol = :symbol",
            shares=new_share_total,
            username=session["username"],
            symbol=symbol)

        else:
            db.execute("INSERT INTO portfolio ( username, symbol, shares) VALUES ( :username, :symbol, :get_shares)",
            username=session["username"],
            symbol=symbol,
            get_shares=get_shares)

        # Record transaction in history db
        db.execute("INSERT INTO history ( username, operation, symbol, price, date, time, shares) VALUES ( :username, 'BUY', :symbol, :price, :date, :time, :shares)",
        username=session['username'],
        symbol=symbol,
        price=price,
        date=date,
        time=time,
        shares=get_shares)

        # Redirect to index
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():

    """Show history of transactions"""

    # Select stocks from history
    stocks = db.execute("SELECT operation, symbol, price, date, time, shares FROM history WHERE username = :username",
    username=session["username"])

    # Loop through stocks assigning values
    for stock in stocks:
        operation = stock['operation']
        symbol = stock['symbol']
        price = stock['price']
        date = stock['date']
        time = stock['time']
        shares = stock['shares']
        stock['price'] = usd(price)

    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():

    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = request.form.get("username")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():

    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get and store form input for easy access
        get_symbol = request.form.get("symbol")

        try:
            stock = lookup(get_symbol)['name']
            price = lookup(get_symbol)['price']
            symbol = lookup(get_symbol)['symbol']
            price = usd(price)

        except:
            return apology(" Must provide a stock symbol")

        else:
            return render_template("quoted.html", stock=stock, price=price, symbol=symbol)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get and store form input for easy access
        get_name = request.form.get("username")
        get_pass = request.form.get("password")
        get_conf = request.form.get("confirmation")

        # Store a hash of password to be used with check_password_hash(pwhash, password)
        hash = generate_password_hash(get_pass, method='pbkdf2:sha256', salt_length=8)

        # Ensure username was submitted
        if not get_name:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not get_pass or not get_conf:
            return apology("must provide password", 403)

        # Check for password length > 8
        elif len(get_pass) < 8:
            return apology("Password must be at least 8 characters")

        # Ensure passwords match
        elif get_pass != get_conf:
            return apology("Passwords must match")

         # Query database for username
        row_name = db.execute("SELECT * FROM users WHERE username = :username",
        username=get_name)

        # Check if queried username is empty
        if len(row_name) != 0:
            return apology("Username already taken :(, ERR {}" .format(row_name[0]["username"]))

        # Insert name and hash into finance database
        else:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
            username=get_name, hash=hash)

        # Redirect user to login page
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get and store form input for easy access
        get_symbol = request.form.get("symbol")
        get_shares = request.form.get("shares")
        dt = datetime.now()
        date = dt.strftime("%x")
        time = dt.strftime("%X")

        # Lookup info for stock and control errors
        try:
            stock = lookup(get_symbol)['name']
            price = lookup(get_symbol)['price']
            symbol = lookup(get_symbol)['symbol']

        except:
            return apology(" Must provide a stock symbol ")

         # Ensure shares submitted
        if not get_shares or int(get_shares) < 1:
            return apology("must provide positive number of shares", 403)

        shares_price = price * float(get_shares)

        # Check if shares already in table
        rows_existing_shares = db.execute("SELECT shares, symbol FROM portfolio WHERE username = :username AND symbol = :symbol",
        username=session["username"],
        symbol=symbol)

        # Loop over all shares
        for share in rows_existing_shares:
            share = share['symbol']

        # Error control - If shares exist Update
        if len(rows_existing_shares) != 0:

            # Error control - Ensure shares are not less than 0

            current_shares = rows_existing_shares[0]['shares']

            new_share_total = float(current_shares) - float(get_shares)

            if new_share_total < 0:
                return apology(" You don't have enough shares :(")

            else:

                # Update shares in portfolio
                db.execute("UPDATE portfolio SET shares = :shares WHERE username = :username AND symbol = :symbol",
                shares=new_share_total,
                username=session["username"],
                symbol=symbol)

                # Update shares in history
                db.execute("UPDATE history SET shares = :shares, operation = 'SELL' WHERE username = :username AND symbol = :symbol",
                shares=new_share_total,
                username=session["username"],
                symbol=symbol)

                # Get cash
                rows_cash = db.execute("SELECT cash FROM users WHERE username = :username",
                username=session["username"])

                cash_available = rows_cash [0]['cash']
                new_total = cash_available + shares_price

                # Update user cash in db
                db.execute("UPDATE users SET cash = :cash WHERE username = :username",
                cash=new_total,
                username=session["username"])

                # Redirect to index
                return redirect("/")

        else:
            return apology("You have no shares")

    # User reached route via GET (as by clicking a link or via redirect)

    # Check if shares already in table send for dropdown menu
    symbols = db.execute("SELECT symbol FROM portfolio WHERE username = :username",
    username=session["username"])

    return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


# Copyright: Matthew Payne Nov-2020
