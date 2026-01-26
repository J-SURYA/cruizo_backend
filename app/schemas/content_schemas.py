from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class ContentUserPublic(BaseModel):
    """
    Schema for content management responses.
    """
    id: str = Field(..., description="User unique identifier")
    username: str = Field(..., description="User's username")
    email: str = Field(..., description="User's email address")

    model_config = ConfigDict(from_attributes=True)


class ContentBase(BaseModel):
    """
    Schema for content blocks supporting multiple content types.
    """
    type: str = Field(..., description="Content type: text, qa, table")
    text: Optional[str] = Field(None, description="Plain text content")
    qa: Optional[Dict[str, Any]] = Field(
        None, description="Question-answer formatted content"
    )
    table: Optional[Dict[str, Any]] = Field(None, description="Tabular data content")


class SectionBase(BaseModel):
    """
    Schema for content sections with ordering.
    """
    title: str = Field(..., max_length=255, description="Section title")
    order: int = Field(..., ge=0, description="Section display order")


class MasterBase(BaseModel):
    """
    Schema for master content documents.
    """
    is_active: bool = Field(
        True, description="Whether this content version is currently active"
    )


class TermsContentCreate(ContentBase):
    """
    Schema for creating terms and conditions content blocks.
    """

    order: int = Field(..., ge=0, description="Content display order within section")


class TermsContentUpdate(ContentBase):
    """
    Schema for updating terms and conditions content blocks.
    """
    order: Optional[int] = Field(
        None, ge=0, description="Content display order within section"
    )


class TermsContentPublic(ContentBase):
    """
    Public schema for terms and conditions content blocks.
    """
    id: int = Field(..., description="Content block unique identifier")
    order: int = Field(..., description="Content display order within section")
    model_config = ConfigDict(from_attributes=True)


class TermsSectionCreate(SectionBase):
    """
    Schema for creating terms and conditions sections.
    """
    contents: List[TermsContentCreate] = Field(
        default_factory=list, description="List of content blocks in this section"
    )


class TermsSectionUpdate(SectionBase):
    """
    Schema for updating terms and conditions sections.
    """
    title: Optional[str] = Field(None, max_length=255, description="Section title")
    order: Optional[int] = Field(None, ge=0, description="Section display order")
    contents: Optional[List[TermsContentCreate]] = Field(
        None, description="List of content blocks in this section"
    )


class TermsSectionPublic(SectionBase):
    """
    Schema for terms and conditions sections.
    """
    id: int = Field(..., description="Section unique identifier")
    contents: List[TermsContentPublic] = Field(
        default_factory=list, description="List of content blocks in this section"
    )
    model_config = ConfigDict(from_attributes=True)


class TermsMasterCreate(MasterBase):
    """
    Schema for creating a new terms and conditions document.
    """
    sections: List[TermsSectionCreate] = Field(
        default_factory=list, description="List of sections in the terms document"
    )


class TermsMasterUpdate(MasterBase):
    """
    Schema for updating an existing terms and conditions document.
    """
    is_active: Optional[bool] = Field(
        None, description="Whether this content version is currently active"
    )
    sections: Optional[List[TermsSectionCreate]] = Field(
        None, description="List of sections in the terms document"
    )


class TermsMasterPublic(MasterBase):
    """
    Schema for terms and conditions documents.
    """
    id: int = Field(..., description="Terms document unique identifier")
    effective_from: datetime = Field(
        ..., description="When this terms version becomes effective"
    )
    last_modified_at: datetime = Field(..., description="Last modification timestamp")
    last_modified_by: str = Field(
        ..., description="User ID who last modified the document"
    )
    sections: List[TermsSectionPublic] = Field(
        default_factory=list, description="List of sections in the terms document"
    )
    modified_by_user: Optional[ContentUserPublic] = Field(
        None, description="User details of the last modifier"
    )
    model_config = ConfigDict(from_attributes=True)


class HelpCentreContentCreate(ContentBase):
    """
    Schema for creating help centre content blocks.
    """
    order: int = Field(..., ge=0, description="Content display order within section")


class HelpCentreContentUpdate(ContentBase):
    """
    Schema for updating help centre content blocks.
    """
    order: Optional[int] = Field(
        None, ge=0, description="Content display order within section"
    )


class HelpCentreContentPublic(ContentBase):
    """
    Schema for help centre content blocks.
    """
    id: int = Field(..., description="Content block unique identifier")
    order: int = Field(..., description="Content display order within section")
    model_config = ConfigDict(from_attributes=True)


class HelpCentreSectionCreate(SectionBase):
    """
    Schema for creating help centre sections.
    """
    contents: List[HelpCentreContentCreate] = Field(
        default_factory=list, description="List of content blocks in this section"
    )


class HelpCentreSectionUpdate(SectionBase):
    """
    Schema for updating help centre sections.
    """
    title: Optional[str] = Field(None, max_length=255, description="Section title")
    order: Optional[int] = Field(None, ge=0, description="Section display order")
    contents: Optional[List[HelpCentreContentCreate]] = Field(
        None, description="List of content blocks in this section"
    )


class HelpCentreSectionPublic(SectionBase):
    """
    Schema for help centre sections.
    """
    id: int = Field(..., description="Section unique identifier")
    contents: List[HelpCentreContentPublic] = Field(
        default_factory=list, description="List of content blocks in this section"
    )
    model_config = ConfigDict(from_attributes=True)


class HelpCentreMasterCreate(MasterBase):
    """
    Schema for creating a new help centre document.
    """
    sections: List[HelpCentreSectionCreate] = Field(
        default_factory=list, description="List of sections in the help centre"
    )


class HelpCentreMasterUpdate(MasterBase):
    """
    Schema for updating an existing help centre document.
    """
    is_active: Optional[bool] = Field(
        None, description="Whether this content version is currently active"
    )
    sections: Optional[List[HelpCentreSectionCreate]] = Field(
        None, description="List of sections in the help centre"
    )


class HelpCentreMasterPublic(MasterBase):
    """
    Schema for help centre documents.
    """
    id: int = Field(..., description="Help centre document unique identifier")
    effective_from: datetime = Field(
        ..., description="When this help centre version becomes effective"
    )
    last_modified_at: datetime = Field(..., description="Last modification timestamp")
    last_modified_by: str = Field(
        ..., description="User ID who last modified the document"
    )
    sections: List[HelpCentreSectionPublic] = Field(
        default_factory=list, description="List of sections in the help centre"
    )
    modified_by_user: Optional[ContentUserPublic] = Field(
        None, description="User details of the last modifier"
    )
    model_config = ConfigDict(from_attributes=True)


class PrivacyPolicyContentCreate(ContentBase):
    """
    Schema for creating privacy policy content blocks.
    """
    order: int = Field(..., ge=0, description="Content display order within section")


class PrivacyPolicyContentUpdate(ContentBase):
    """
    Schema for updating privacy policy content blocks.
    """
    order: Optional[int] = Field(
        None, ge=0, description="Content display order within section"
    )


class PrivacyPolicyContentPublic(ContentBase):
    """
    Schema for privacy policy content blocks.
    """
    id: int = Field(..., description="Content block unique identifier")
    order: int = Field(..., description="Content display order within section")
    model_config = ConfigDict(from_attributes=True)


class PrivacyPolicySectionCreate(SectionBase):
    """
    Schema for creating privacy policy sections.
    """
    contents: List[PrivacyPolicyContentCreate] = Field(
        default_factory=list, description="List of content blocks in this section"
    )


class PrivacyPolicySectionUpdate(SectionBase):
    """
    Schema for updating privacy policy sections.
    """
    title: Optional[str] = Field(None, max_length=255, description="Section title")
    order: Optional[int] = Field(None, ge=0, description="Section display order")
    contents: Optional[List[PrivacyPolicyContentCreate]] = Field(
        None, description="List of content blocks in this section"
    )


class PrivacyPolicySectionPublic(SectionBase):
    """
    Schema for privacy policy sections.
    """
    id: int = Field(..., description="Section unique identifier")
    contents: List[PrivacyPolicyContentPublic] = Field(
        default_factory=list, description="List of content blocks in this section"
    )
    model_config = ConfigDict(from_attributes=True)


class PrivacyPolicyMasterCreate(MasterBase):
    """
    Schema for creating a new privacy policy document.
    """
    sections: List[PrivacyPolicySectionCreate] = Field(
        default_factory=list, description="List of sections in the privacy policy"
    )


class PrivacyPolicyMasterUpdate(MasterBase):
    """
    Schema for updating an existing privacy policy document.
    """
    is_active: Optional[bool] = Field(
        None, description="Whether this content version is currently active"
    )
    sections: Optional[List[PrivacyPolicySectionCreate]] = Field(
        None, description="List of sections in the privacy policy"
    )


class PrivacyPolicyMasterPublic(MasterBase):
    """
    Schema for privacy policy documents.
    """
    id: int = Field(..., description="Privacy policy document unique identifier")
    effective_from: datetime = Field(
        ..., description="When this privacy policy version becomes effective"
    )
    last_modified_at: datetime = Field(..., description="Last modification timestamp")
    last_modified_by: str = Field(
        ..., description="User ID who last modified the document"
    )
    sections: List[PrivacyPolicySectionPublic] = Field(
        default_factory=list, description="List of sections in the privacy policy"
    )
    modified_by_user: Optional[ContentUserPublic] = Field(
        None, description="User details of the last modifier"
    )
    model_config = ConfigDict(from_attributes=True)


class FAQContentCreate(ContentBase):
    """
    Schema for creating FAQ content blocks.
    """
    order: int = Field(..., ge=0, description="Content display order within section")


class FAQContentUpdate(ContentBase):
    """
    Schema for updating FAQ content blocks.
    """
    order: Optional[int] = Field(
        None, ge=0, description="Content display order within section"
    )


class FAQContentPublic(ContentBase):
    """
    Schema for FAQ content blocks.
    """
    id: int = Field(..., description="Content block unique identifier")
    order: int = Field(..., description="Content display order within section")
    model_config = ConfigDict(from_attributes=True)


class FAQSectionCreate(SectionBase):
    """
    Schema for creating FAQ sections.
    """
    contents: List[FAQContentCreate] = Field(
        default_factory=list, description="List of content blocks in this section"
    )


class FAQSectionUpdate(SectionBase):
    """
    Schema for updating FAQ sections.
    """
    title: Optional[str] = Field(None, max_length=255, description="Section title")
    order: Optional[int] = Field(None, ge=0, description="Section display order")
    contents: Optional[List[FAQContentCreate]] = Field(
        None, description="List of content blocks in this section"
    )


class FAQSectionPublic(SectionBase):
    """
    Schema for FAQ sections.
    """
    id: int = Field(..., description="Section unique identifier")
    contents: List[FAQContentPublic] = Field(
        default_factory=list, description="List of content blocks in this section"
    )
    model_config = ConfigDict(from_attributes=True)


class FAQMasterCreate(MasterBase):
    """
    Schema for creating a new FAQ document.
    """
    sections: List[FAQSectionCreate] = Field(
        default_factory=list, description="List of sections in the FAQ"
    )


class FAQMasterUpdate(MasterBase):
    """
    Schema for updating an existing FAQ document.
    """
    is_active: Optional[bool] = Field(
        None, description="Whether this content version is currently active"
    )
    sections: Optional[List[FAQSectionCreate]] = Field(
        None, description="List of sections in the FAQ"
    )


class FAQMasterPublic(MasterBase):
    """
    Schema for FAQ documents.
    """
    id: int = Field(..., description="FAQ document unique identifier")
    effective_from: datetime = Field(
        ..., description="When this FAQ version becomes effective"
    )
    last_modified_at: datetime = Field(..., description="Last modification timestamp")
    last_modified_by: str = Field(
        ..., description="User ID who last modified the document"
    )
    sections: List[FAQSectionPublic] = Field(
        default_factory=list, description="List of sections in the FAQ"
    )
    modified_by_user: Optional[ContentUserPublic] = Field(
        None, description="User details of the last modifier"
    )
    model_config = ConfigDict(from_attributes=True)


class HomePagePromotionCreate(BaseModel):
    """
    Schema for creating homepage promotion banners.
    """
    title: str = Field(..., max_length=255, description="Promotion title")
    subtitle: str = Field(..., max_length=255, description="Promotion subtitle")
    description: str = Field(..., description="Promotion detailed description")
    discount: str = Field(
        ..., max_length=10, description="Discount percentage or amount"
    )
    timeline: datetime = Field(..., description="Promotion expiration date")
    type: str = Field(..., description="Promotion type")


class HomePagePromotionUpdate(BaseModel):
    """
    Schema for updating homepage promotion banners.
    """
    title: Optional[str] = Field(None, max_length=255, description="Promotion title")
    subtitle: Optional[str] = Field(
        None, max_length=255, description="Promotion subtitle"
    )
    description: Optional[str] = Field(
        None, description="Promotion detailed description"
    )
    discount: Optional[str] = Field(
        None, max_length=10, description="Discount percentage or amount"
    )
    timeline: Optional[datetime] = Field(None, description="Promotion expiration date")
    type: Optional[str] = Field(None, description="Promotion type")


class HomePagePromotionPublic(HomePagePromotionCreate):
    """
    Schema for homepage promotion banners.
    """
    id: int = Field(..., description="Promotion unique identifier")
    model_config = ConfigDict(from_attributes=True)


class HomePageCarCategoryCreate(BaseModel):
    """
    Schema for creating homepage car category displays.
    """
    title: str = Field(..., max_length=255, description="Category title")
    description: Optional[str] = Field(None, description="Category description")
    price_range: Optional[str] = Field(
        None, description="Price range for this category"
    )
    image_url: Optional[str] = Field(None, description="Category image URL")


class HomePageCarCategoryUpdate(BaseModel):
    """
    Schema for updating homepage car category displays.
    """
    title: Optional[str] = Field(None, max_length=255, description="Category title")
    description: Optional[str] = Field(None, description="Category description")
    price_range: Optional[str] = Field(
        None, description="Price range for this category"
    )
    image_url: Optional[str] = Field(None, description="Category image URL")


class HomePageCarCategoryPublic(HomePageCarCategoryCreate):
    """
    Public schema for homepage car category displays.
    """
    id: int = Field(..., description="Category unique identifier")
    model_config = ConfigDict(from_attributes=True)


class HomePageContactFAQCreate(BaseModel):
    """
    Schema for creating homepage contact section FAQs.
    """
    order: int = Field(..., ge=0, description="FAQ display order")
    question: str = Field(..., description="FAQ question")
    answer: str = Field(..., description="FAQ answer")


class HomePageContactFAQUpdate(BaseModel):
    """
    Schema for updating homepage contact section FAQs.
    """
    order: Optional[int] = Field(None, ge=0, description="FAQ display order")
    question: Optional[str] = Field(None, description="FAQ question")
    answer: Optional[str] = Field(None, description="FAQ answer")


class HomePageContactFAQPublic(HomePageContactFAQCreate):
    """
    Schema for homepage contact section FAQs.
    """

    id: int = Field(..., description="FAQ unique identifier")
    model_config = ConfigDict(from_attributes=True)


class HomePageCarEssential(BaseModel):
    """
    Schema for essential car information for homepage display.
    """
    id: int = Field(..., description="Car unique identifier")
    car_no: str = Field(..., description="Car license plate number")
    brand: str = Field(..., description="Car brand")
    model: str = Field(..., description="Car model")
    color: str = Field(..., description="Car color")
    mileage: int = Field(..., description="Car mileage")
    rental_per_hr: float = Field(..., description="Rental price per hour")
    manufacture_year: int = Field(..., description="Manufacture year")
    image_url: List[str] = Field(..., description="List of car image URLs")
    transmission_type: str = Field(..., description="Transmission type")

    category_name: Optional[str] = Field(None, description="Car category name")
    fuel_name: Optional[str] = Field(None, description="Fuel type name")
    capacity_value: Optional[int] = Field(None, description="Seating capacity")
    feature_names: List[str] = Field(
        default_factory=list, description="List of feature names"
    )

    model_config = ConfigDict(from_attributes=True)


class HomePageTopRentalCreate(BaseModel):
    """
    Schema for creating homepage top rental car association.
    """
    car_id: int = Field(..., description="Car ID to feature")
    display_order: int = Field(0, ge=0, description="Display order for sorting")


class HomePageTopRentalUpdate(BaseModel):
    """
    Schema for updating homepage top rental car association.
    """
    car_id: Optional[int] = Field(None, description="Car ID to feature")
    display_order: Optional[int] = Field(
        None, ge=0, description="Display order for sorting"
    )


class HomePageTopRentalPublic(BaseModel):
    """
    Schema for homepage top rental car association.
    """
    id: int = Field(..., description="Association unique identifier")
    car_id: int = Field(..., description="Car ID")
    display_order: int = Field(..., description="Display order for sorting")
    car: HomePageCarEssential = Field(
        ..., description="Essential car details with features"
    )

    model_config = ConfigDict(from_attributes=True)


class HomePageReviewEssential(BaseModel):
    """
    Schema for essential review information for homepage display.
    """
    id: int = Field(..., description="Review unique identifier")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    remarks: Optional[str] = Field(None, description="Review comments")
    created_at: datetime = Field(..., description="Review creation timestamp")
    reviewer_name: Optional[str] = Field(None, description="Reviewer's username")
    reviewer_email: Optional[str] = Field(None, description="Reviewer's email")
    car_brand: Optional[str] = Field(None, description="Reviewed car brand")
    car_model: Optional[str] = Field(None, description="Reviewed car model")

    model_config = ConfigDict(from_attributes=True)


class HomePageFeaturedReviewCreate(BaseModel):
    """
    Schema for creating homepage featured review association.
    """
    review_id: int = Field(..., description="Review ID to feature")
    display_order: int = Field(0, ge=0, description="Display order for sorting")


class HomePageFeaturedReviewUpdate(BaseModel):
    """
    Schema for updating homepage featured review association.
    """
    review_id: Optional[int] = Field(None, description="Review ID to feature")
    display_order: Optional[int] = Field(
        None, ge=0, description="Display order for sorting"
    )


class HomePageFeaturedReviewPublic(BaseModel):
    """
    Schema for homepage featured review association.
    """
    id: int = Field(..., description="Association unique identifier")
    review_id: int = Field(..., description="Review ID")
    display_order: int = Field(..., description="Display order for sorting")
    review: HomePageReviewEssential = Field(..., description="Essential review details")

    model_config = ConfigDict(from_attributes=True)


class HomePageCreate(BaseModel):
    """
    Schema for creating a new homepage configuration.
    """
    is_active: bool = Field(True, description="Whether this homepage version is active")
    hero_section: Optional[Dict[str, Any]] = Field(
        None, description="Hero section configuration"
    )
    about_section: Optional[Dict[str, Any]] = Field(
        None, description="About section configuration"
    )
    promotions_section: Optional[Dict[str, Any]] = Field(
        None, description="Promotions section configuration"
    )
    promotions: List[HomePagePromotionCreate] = Field(
        default_factory=list, description="List of promotions"
    )
    top_rental_section: Optional[Dict[str, Any]] = Field(
        None, description="Top rental cars section configuration"
    )
    top_rentals: List[HomePageTopRentalCreate] = Field(
        default_factory=list, description="List of top rental car associations"
    )
    explore_cars_section: Optional[Dict[str, Any]] = Field(
        None, description="Explore cars section configuration"
    )
    explore_cars_categories: List[HomePageCarCategoryCreate] = Field(
        default_factory=list, description="List of car categories"
    )
    reviews_section: Optional[Dict[str, Any]] = Field(
        None, description="Reviews section configuration"
    )
    featured_reviews: List[HomePageFeaturedReviewCreate] = Field(
        default_factory=list, description="List of featured review associations"
    )
    contact_section: Optional[Dict[str, Any]] = Field(
        None, description="Contact section configuration"
    )
    contact_faqs: List[HomePageContactFAQCreate] = Field(
        default_factory=list, description="List of contact FAQs"
    )
    footer_section: Optional[Dict[str, Any]] = Field(
        None, description="Footer section configuration"
    )


class HomePageUpdate(BaseModel):
    """
    Schema for updating an existing homepage configuration.
    """
    is_active: Optional[bool] = Field(
        None, description="Whether this homepage version is active"
    )
    hero_section: Optional[Dict[str, Any]] = Field(
        None, description="Hero section configuration"
    )
    about_section: Optional[Dict[str, Any]] = Field(
        None, description="About section configuration"
    )
    promotions_section: Optional[Dict[str, Any]] = Field(
        None, description="Promotions section configuration"
    )
    promotions: Optional[List[HomePagePromotionCreate]] = Field(
        None, description="List of promotions"
    )
    top_rental_section: Optional[Dict[str, Any]] = Field(
        None, description="Top rental cars section configuration"
    )
    top_rentals: Optional[List[HomePageTopRentalCreate]] = Field(
        None, description="List of top rental car associations"
    )
    explore_cars_section: Optional[Dict[str, Any]] = Field(
        None, description="Explore cars section configuration"
    )
    explore_cars_categories: Optional[List[HomePageCarCategoryCreate]] = Field(
        None, description="List of car categories"
    )
    reviews_section: Optional[Dict[str, Any]] = Field(
        None, description="Reviews section configuration"
    )
    featured_reviews: Optional[List[HomePageFeaturedReviewCreate]] = Field(
        None, description="List of featured review associations"
    )
    contact_section: Optional[Dict[str, Any]] = Field(
        None, description="Contact section configuration"
    )
    contact_faqs: Optional[List[HomePageContactFAQCreate]] = Field(
        None, description="List of contact FAQs"
    )
    footer_section: Optional[Dict[str, Any]] = Field(
        None, description="Footer section configuration"
    )


class HomePagePublic(BaseModel):
    """
    Schema for homepage configurations with full related data.
    """
    id: int = Field(..., description="Homepage configuration unique identifier")
    is_active: bool = Field(..., description="Whether this homepage version is active")
    effective_from: datetime = Field(
        ..., description="When this homepage version becomes effective"
    )
    last_modified_at: datetime = Field(..., description="Last modification timestamp")
    last_modified_by: Optional[str] = Field(
        None, description="User ID who last modified the homepage"
    )
    hero_section: Optional[Dict[str, Any]] = Field(
        None, description="Hero section configuration"
    )
    about_section: Optional[Dict[str, Any]] = Field(
        None, description="About section configuration"
    )
    promotions_section: Optional[Dict[str, Any]] = Field(
        None, description="Promotions section configuration"
    )
    promotions: List[HomePagePromotionPublic] = Field(
        default_factory=list, description="List of promotions"
    )
    top_rental_section: Optional[Dict[str, Any]] = Field(
        None, description="Top rental cars section configuration"
    )
    top_rentals: List[HomePageTopRentalPublic] = Field(
        default_factory=list, description="List of top rental cars with full details"
    )
    explore_cars_section: Optional[Dict[str, Any]] = Field(
        None, description="Explore cars section configuration"
    )
    explore_cars_categories: List[HomePageCarCategoryPublic] = Field(
        default_factory=list, description="List of car categories"
    )
    reviews_section: Optional[Dict[str, Any]] = Field(
        None, description="Reviews section configuration"
    )
    featured_reviews: List[HomePageFeaturedReviewPublic] = Field(
        default_factory=list, description="List of featured reviews with full details"
    )
    contact_section: Optional[Dict[str, Any]] = Field(
        None, description="Contact section configuration"
    )
    contact_faqs: List[HomePageContactFAQPublic] = Field(
        default_factory=list, description="List of contact FAQs"
    )
    footer_section: Optional[Dict[str, Any]] = Field(
        None, description="Footer section configuration"
    )
    modified_by_user: Optional[ContentUserPublic] = Field(
        None, description="User details of the last modifier"
    )

    model_config = ConfigDict(from_attributes=True)


class PaginatedTermsResponse(BaseModel):
    """
    Schema for paginated response of terms and conditions documents.
    """
    total: int = Field(..., description="Total number of terms documents")
    items: List[TermsMasterPublic] = Field(..., description="List of terms documents")


class PaginatedHelpCentreResponse(BaseModel):
    """
    Schema for paginated response of help centre documents.
    """
    total: int = Field(..., description="Total number of help centre documents")
    items: List[HelpCentreMasterPublic] = Field(
        ..., description="List of help centre documents"
    )


class PaginatedPrivacyPolicyResponse(BaseModel):
    """
    Schema for paginated response of privacy policy documents.
    """
    total: int = Field(..., description="Total number of privacy policy documents")
    items: List[PrivacyPolicyMasterPublic] = Field(
        ..., description="List of privacy policy documents"
    )


class PaginatedFAQResponse(BaseModel):
    """
    Schema for paginated response of FAQ documents.
    """
    total: int = Field(..., description="Total number of FAQ documents")
    items: List[FAQMasterPublic] = Field(..., description="List of FAQ documents")


class PaginatedHomePageResponse(BaseModel):
    """
    Schema for paginated response of homepage configurations.
    """
    total: int = Field(..., description="Total number of homepage configurations")
    items: List[HomePagePublic] = Field(
        ..., description="List of homepage configurations"
    )


class SetActiveRequest(BaseModel):
    """
    Schema for setting a content document as active.
    """
    id: int = Field(..., description="ID of the content to set as active")


class AdminHelpCentreContentBase(BaseModel):
    """
    Schema for admin help centre content blocks supporting multiple content types.
    """
    type: str = Field(..., description="Content type: text, qa, table, tip, warning")
    text: Optional[str] = Field(None, description="Plain text content")
    qa: Optional[Dict[str, Any]] = Field(
        None, description="Question-answer formatted content"
    )
    table: Optional[Dict[str, Any]] = Field(None, description="Tabular data content")


class AdminHelpCentreContentCreate(AdminHelpCentreContentBase):
    """
    Schema for creating admin help centre content blocks.
    """
    order: int = Field(..., ge=0, description="Content display order within section")


class AdminHelpCentreContentUpdate(AdminHelpCentreContentBase):
    """
    Schema for updating admin help centre content blocks.
    """
    order: Optional[int] = Field(
        None, ge=0, description="Content display order within section"
    )


class AdminHelpCentreContentPublic(AdminHelpCentreContentBase):
    """
    Schema for admin help centre content blocks.
    """
    id: int = Field(..., description="Content block unique identifier")
    order: int = Field(..., description="Content display order within section")
    model_config = ConfigDict(from_attributes=True)


class AdminHelpCentreSectionCreate(BaseModel):
    """
    Schema for creating admin help centre sections.
    """
    title: str = Field(..., max_length=255, description="Section title")
    order: int = Field(..., ge=0, description="Section display order")
    icon: Optional[str] = Field(
        None, max_length=100, description="FontAwesome icon class"
    )
    contents: List[AdminHelpCentreContentCreate] = Field(
        default_factory=list, description="List of content blocks in this section"
    )


class AdminHelpCentreSectionUpdate(BaseModel):
    """
    Schema for updating admin help centre sections.
    """
    title: Optional[str] = Field(None, max_length=255, description="Section title")
    order: Optional[int] = Field(None, ge=0, description="Section display order")
    icon: Optional[str] = Field(
        None, max_length=100, description="FontAwesome icon class"
    )
    contents: Optional[List[AdminHelpCentreContentCreate]] = Field(
        None, description="List of content blocks in this section"
    )


class AdminHelpCentreSectionPublic(BaseModel):
    """
    Schema for admin help centre sections.
    """
    id: int = Field(..., description="Section unique identifier")
    title: str = Field(..., description="Section title")
    order: int = Field(..., description="Section display order")
    icon: Optional[str] = Field(None, description="FontAwesome icon class")
    contents: List[AdminHelpCentreContentPublic] = Field(
        default_factory=list, description="List of content blocks in this section"
    )
    model_config = ConfigDict(from_attributes=True)


class AdminHelpCentreMasterCreate(MasterBase):
    """
    Schema for creating a new admin help centre document.
    """
    sections: List[AdminHelpCentreSectionCreate] = Field(
        default_factory=list, description="List of sections in the admin help centre"
    )


class AdminHelpCentreMasterUpdate(MasterBase):
    """
    Schema for updating an existing admin help centre document.
    """
    is_active: Optional[bool] = Field(
        None, description="Whether this content version is currently active"
    )
    sections: Optional[List[AdminHelpCentreSectionCreate]] = Field(
        None, description="List of sections in the admin help centre"
    )


class AdminHelpCentreMasterPublic(MasterBase):
    """
    Schema for admin help centre documents.
    """
    id: int = Field(..., description="Admin help centre document unique identifier")
    effective_from: datetime = Field(
        ..., description="When this admin help centre version becomes effective"
    )
    last_modified_at: datetime = Field(..., description="Last modification timestamp")
    last_modified_by: str = Field(
        ..., description="User ID who last modified the document"
    )
    sections: List[AdminHelpCentreSectionPublic] = Field(
        default_factory=list, description="List of sections in the admin help centre"
    )
    modified_by_user: Optional[ContentUserPublic] = Field(
        None, description="User details of the last modifier"
    )
    model_config = ConfigDict(from_attributes=True)


class PaginatedAdminHelpCentreResponse(BaseModel):
    """
    Schema for paginated response of admin help centre documents.
    """
    total: int = Field(..., description="Total number of admin help centre documents")
    items: List[AdminHelpCentreMasterPublic] = Field(
        ..., description="List of admin help centre documents"
    )
