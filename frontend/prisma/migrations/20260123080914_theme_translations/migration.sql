/*
  Warnings:

  - Made the column `dataSource` on table `surveys` required. This step will fail if there are existing NULL values in that column.

*/
-- AlterTable
ALTER TABLE "surveys" ALTER COLUMN "dataSource" SET NOT NULL;

-- CreateTable
CREATE TABLE "theme_translations" (
    "id" TEXT NOT NULL,
    "theme_id" TEXT NOT NULL,
    "locale" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "about_button_title" TEXT NOT NULL,
    "about_button_text" TEXT NOT NULL,
    "success_stories_title" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "theme_translations_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "theme_translations_theme_id_locale_key" ON "theme_translations"("theme_id", "locale");

-- AddForeignKey
ALTER TABLE "theme_translations" ADD CONSTRAINT "theme_translations_theme_id_fkey" FOREIGN KEY ("theme_id") REFERENCES "themes"("id") ON DELETE CASCADE ON UPDATE CASCADE;
