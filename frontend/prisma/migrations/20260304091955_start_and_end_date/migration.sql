/*
  Warnings:

  - You are about to drop the column `date` on the `dates` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "dates" DROP COLUMN "date",
ADD COLUMN     "end_date" TIMESTAMP(3),
ADD COLUMN     "start_date" TIMESTAMP(3);
