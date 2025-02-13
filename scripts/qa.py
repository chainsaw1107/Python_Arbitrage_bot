from langchain_community.utilities import SQLDatabase

from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI

import os

database_url = os.environ.get("DATABASE_URL")

db = SQLDatabase.from_uri(database_url)
print(db.dialect)
print(db.get_usable_table_names())

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

from operator import itemgetter

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool


from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

system = """You are a {dialect} expert. Given an input question, creat a syntactically correct {dialect} query to run.
Unless the user specifies in the question a specific number of examples to obtain, query for at most {top_k} results using the LIMIT clause as per {dialect}. You can order the results to return the most informative data in the database.
Never query for all columns from a table. You must query only the columns that are needed to answer the question. Wrap each column name in double quotes (") to denote them as delimited identifiers.
Pay attention to use only the column names you can see in the tables below. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
Pay attention to use date('now') function to get the current date, if the question involves "today".

Only use the following tables:
{table_info}

Write an initial draft of the query. Then double check the {dialect} query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins
- do not add random LIMIT clauses!
- this query will be used in a grafana dashboard, so make sure the output is in a format that can be easily visualized.
- NOTE not all data should presented in a time series format, some data should be presented in a table format.
- NOTE the data should be presented in a way that is easy to understand for a non-technical user.


Use format:

First draft: <<FIRST_DRAFT_QUERY>>
Final answer: <<FINAL_ANSWER_QUERY>>
"""
prompt = ChatPromptTemplate.from_messages(
    [("system", system), ("human", "{input}")]
).partial(dialect=db.dialect)


def parse_final_answer(output: str) -> str:
    sql = output.split("Final answer: ")[1]
    # we then remove the "```sql" and "```" from the string
    sql = sql.replace("```sql", "").replace("```", "")
    print("SQL: ", sql)
    return sql


chain = create_sql_query_chain(llm, db, prompt=prompt) | parse_final_answer

from rich import print

while True:
    question = input("Ask a question: ")
    response = chain.invoke({"question": question})
    result = db.run(response)
    # we then chain the output to the output parser
    output_parser = StrOutputParser()
    result = output_parser.invoke(result)
    # we then print the output
    print(result)
