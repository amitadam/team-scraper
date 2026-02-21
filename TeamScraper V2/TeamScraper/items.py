import scrapy


class EmployeeItem(scrapy.Item):
    """
    Item for storing employee/team member information
    """
    # Core fields
    name = scrapy.Field()
    email = scrapy.Field()
    position = scrapy.Field()  # NEW: Job title/position
    
    # Source tracking
    company_url = scrapy.Field()  # The main URL being scraped
    page_url = scrapy.Field()     # The specific page where this person was found
