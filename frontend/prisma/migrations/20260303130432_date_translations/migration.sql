-- CreateTable
CREATE TABLE "date_translations" (
    "id" TEXT NOT NULL,
    "date_id" TEXT NOT NULL,
    "locale" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "date_translations_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "date_translations_date_id_locale_key" ON "date_translations"("date_id", "locale");

-- AddForeignKey
ALTER TABLE "date_translations" ADD CONSTRAINT "date_translations_date_id_fkey" FOREIGN KEY ("date_id") REFERENCES "dates"("id") ON DELETE CASCADE ON UPDATE CASCADE;
