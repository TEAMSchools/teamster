import json

from py_avro_schema import generate
from pydantic import BaseModel


class Info(BaseModel):
    title: str | None = None
    description: str | None = None
    documentTitle: str | None = None


class TextQuestion(BaseModel):
    paragraph: bool | None = None


class Option(BaseModel):
    value: str | None = None
    goToAction: str | None = None
    goToSectionId: str | None = None


class ChoiceQuestion(BaseModel):
    type: str | None = None

    options: list[Option | None] | None = None


class FileUploadQuestion(BaseModel):
    folderId: str | None = None
    maxFiles: int | None = None
    maxFileSize: str | None = None

    types: list[str | None] | None = None


class DateQuestion(BaseModel):
    includeYear: bool | None = None


class RowQuestion(BaseModel):
    title: str | None = None


class Question(BaseModel):
    questionId: str | None = None
    required: bool | None = None

    choiceQuestion: ChoiceQuestion | None = None
    dateQuestion: DateQuestion | None = None
    fileUploadQuestion: FileUploadQuestion | None = None
    grading: Grading | None = None
    rowQuestion: RowQuestion | None = None
    scaleQuestion: ScaleQuestion | None = None
    textQuestion: TextQuestion | None = None
    timeQuestion: TimeQuestion | None = None


class MediaProperties(BaseModel):
    alignment: str | None = None
    width: int | None = None


class Image(BaseModel):
    contentUri: str | None = None
    altText: str | None = None
    sourceUri: str | None = None
    properties: MediaProperties | None = None


class QuestionItem(BaseModel):
    question: Question | None = None
    image: Image | None = None


class Columns(BaseModel):
    type: str | None = None
    options: list[Option | None] | None = None


class Grid(BaseModel):
    columns: Columns | None = None


class QuestionGroupItem(BaseModel):
    questions: list[Question | None] | None = None
    grid: Grid | None = None


class PageBreakItem(BaseModel): ...


class TextItem(BaseModel): ...


class ImageItem(BaseModel):
    image: Image | None = None


class Video(BaseModel):
    youtubeUri: str | None = None
    properties: MediaProperties | None = None


class VideoItem(BaseModel):
    caption: str | None = None
    video: Video | None = None


class Item(BaseModel):
    itemId: str | None = None
    title: str | None = None
    description: str | None = None

    questionItem: QuestionItem | None = None
    questionGroupItem: QuestionGroupItem | None = None
    pageBreakItem: PageBreakItem | None = None
    textItem: TextItem | None = None
    imageItem: ImageItem | None = None
    videoItem: VideoItem | None = None


class QuizSettings(BaseModel):
    isQuiz: bool | None = None


class FormSettings(BaseModel):
    quizSettings: QuizSettings | None = None


class Form(BaseModel):
    formId: str | None = None
    revisionId: str | None = None
    responderUri: str | None = None
    linkedSheetId: str | None = None

    info: Info | None = None
    settings: FormSettings | None = None

    items: list[Item | None] | None = None


class TextLink(BaseModel):
    uri: str | None = None
    displayText: str | None = None


class VideoLink(BaseModel):
    displayText: str | None = None
    youtubeUri: str | None = None


class ExtraMaterial(BaseModel):
    link: TextLink | None = None
    video: VideoLink | None = None


class Feedback(BaseModel):
    text: str | None = None
    material: list[ExtraMaterial | None] | None = None


class Grade(BaseModel):
    score: float | None = None
    correct: bool | None = None
    feedback: Feedback | None = None


class TextAnswer(BaseModel):
    value: str | None = None


class TextAnswers(BaseModel):
    answers: list[TextAnswer | None] | None = None


class FileUploadAnswer(BaseModel):
    fileId: str | None = None
    fileName: str | None = None
    mimeType: str | None = None


class FileUploadAnswers(BaseModel):
    answers: list[FileUploadAnswer | None] | None = None


class Answer(BaseModel):
    questionId: str | None = None

    grade: Grade | None = None
    textAnswers: TextAnswers | None = None
    fileUploadAnswers: FileUploadAnswers | None = None


class Response(BaseModel):
    formId: str | None = None
    responseId: str | None = None
    createTime: str | None = None
    lastSubmittedTime: str | None = None
    respondentEmail: str | None = None
    totalScore: float | None = None

    answers: dict[str, Answer] | None = None


ASSET_FIELDS = {
    "form": json.loads(generate(py_type=Form, namespace="form")),
    "responses": json.loads(generate(py_type=Response, namespace="response")),
}
